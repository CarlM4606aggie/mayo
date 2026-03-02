import os
import json
import re
import requests
import hmac
import hashlib
import time
from flask import Flask, request, jsonify
from github import Github, GithubIntegration
from github.Repository import Repository # Import for type hinting
from github.Issue import Issue # Import for type hinting
from typing import Dict, List, Tuple, Union # Import for type hinting

app = Flask(__name__)

# Config
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
APP_ID = os.environ.get('APP_ID')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY', '').replace('\n', '\n')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET')
# GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Constants for repository structure fetching
MAX_REPO_STRUCTURE_DEPTH: int = 1
MAX_REPO_STRUCTURE_ITEMS_PER_DIR: int = 30

# Helper: Verify Webhook Signature
def verify_signature(req: request) -> bool:
    """
    Verifies the GitHub webhook signature.
    
    Args:
        req: The Flask request object.
        
    Returns:
        True if the signature is valid, False otherwise.
    """
    signature = req.headers.get('X-Hub-Signature-256')
    if not signature or not WEBHOOK_SECRET:
        return False
    
    sha_name, signature = signature.split('=')
    if sha_name != 'sha256':
        return False
    
    mac = hmac.new(WEBHOOK_SECRET.encode(), req.data, hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

# Helper: Get GitHub Client for Installation
def get_installation_token(installation_id: int) -> str:
    """
    Retrieves an access token for a given GitHub App installation.
    
    Args:
        installation_id: The ID of the GitHub App installation.
        
    Returns:
        The installation's access token.
    """
    integration = GithubIntegration(APP_ID, PRIVATE_KEY)
    return integration.get_access_token(installation_id).token

def get_github_client(installation_id: int) -> Github:
    """
    Creates a PyGithub client instance for a specific installation.
    
    Args:
        installation_id: The ID of the GitHub App installation.
        
    Returns:
        A Github client instance authenticated for the installation.
    """
    token = get_installation_token(installation_id)
    return Github(token)

# Helper: Get Bot Login
BOT_LOGIN_CACHE: Union[str, None] = None
def get_bot_login() -> str:
    """
    Retrieves the GitHub login of the bot. Caches the result.
    
    Returns:
        The bot's GitHub login (e.g., "joe-gemini-bot[bot]").
    """
    global BOT_LOGIN_CACHE
    if BOT_LOGIN_CACHE:
        return BOT_LOGIN_CACHE
    try:
        integration = GithubIntegration(APP_ID, PRIVATE_KEY)
        BOT_LOGIN_CACHE = f"{integration.get_app().slug}[bot]"
        return BOT_LOGIN_CACHE
    except Exception as e:
        print(f"Error getting bot login: {e}")
        return "joe-gemini-bot[bot]" # Fallback

def fetch_memory(repo: Repository, issue_number: int, bot_login: str) -> Dict[str, Union[List[str], str]]:
    """
    Reads bot's previous comments on an issue and extracts [MEMORY] blocks.
    
    Args:
        repo: The GitHub repository object.
        issue_number: The number of the issue to fetch memory from.
        bot_login: The GitHub login of the bot.
        
    Returns:
        A dictionary containing 'files_read' (list of paths) and 'context_summary' (string).
    """
    try:
        issue: Issue = repo.get_issue(number=issue_number)
        memory_data: Dict[str, Union[List[str], str]] = {
            "files_read": [],
            "context_summary": ""
        }
        
        for comment in issue.get_comments():
            if comment.user.login.lower() == bot_login.lower():
                body = comment.body
                # Look for hidden memory block
                memory_match = re.search(r'<!-- \[MEMORY\]([\s\S]*?)\[/MEMORY\] -->', body)
                if memory_match:
                    try:
                        mem = json.loads(memory_match.group(1).strip())
                        if 'files_read' in mem and isinstance(mem['files_read'], list):
                            # Ensure all items in files_read are strings before extending
                            memory_data['files_read'].extend([f for f in mem['files_read'] if isinstance(f, str)])
                        if 'context_summary' in mem and isinstance(mem['context_summary'], str):
                            memory_data['context_summary'] = mem['context_summary']
                    except json.JSONDecodeError:
                        pass
        
        # Deduplicate files
        memory_data['files_read'] = list(set(memory_data['files_read'])) # type: ignore
        return memory_data
    except Exception as e:
        print(f"Memory fetch error: {e}")
        return {"files_read": [], "context_summary": ""}

def format_memory_block(data: Dict) -> str:
    """
    Format memory data as a hidden HTML comment.
    
    Args:
        data: The dictionary containing memory information.
        
    Returns:
        A string formatted as a hidden HTML comment.
    """
    return f"\n\n<!-- [MEMORY]{json.dumps(data)}[/MEMORY] -->"

def get_repo_structure(repo: Repository, path: str = "", max_depth: int = MAX_REPO_STRUCTURE_DEPTH, current_depth: int = 0) -> str:
    """
    Get repository file structure via GitHub API.
    
    Args:
        repo: The GitHub repository object.
        path: The path within the repository to start listing from.
        max_depth: The maximum depth to traverse into directories.
        current_depth: The current recursion depth (for internal use).
        
    Returns:
        A string representing the file and directory structure.
    """
    if current_depth > max_depth:
        return ""
    
    structure = ""
    try:
        contents = repo.get_contents(path)
        # Sort: dirs first, then files
        items = sorted(contents, key=lambda x: (x.type != 'dir', x.name))
        
        for item in items[:MAX_REPO_STRUCTURE_ITEMS_PER_DIR]:  # Limit items per directory to avoid timeout
            if item.name.startswith('.'):
                continue
            
            indent = "  " * current_depth
            marker = "📁 " if item.type == 'dir' else "📄 "
            structure += f"{indent}{marker}{item.name}\n"
            
            # Only go up to max_depth deep
            if item.type == 'dir' and current_depth < max_depth:
                structure += get_repo_structure(repo, item.path, max_depth, current_depth + 1)
    except Exception as e:
        print(f"Repo structure error: {e}")
        structure = f"Error: {e}\n"
    
    return structure

def parse_diff_files(diff_text: str) -> List[Dict[str, Union[str, List[Tuple[int, int]]]]]:
    """
    Parse unified diff to extract changed files with their line ranges.
    
    Args:
        diff_text: The unified diff string.
        
    Returns:
        A list of dictionaries, where each dictionary represents a changed file
        and contains its 'path' and a list of 'lines' (line range tuples).
        Example: [{'path': 'file.py', 'lines': [(10, 20), (30, 35)]}]
    """
    files: List[Dict[str, Union[str, List[Tuple[int, int]]]]] = []
    current_file: Union[str, None] = None
    current_lines: List[Tuple[int, int]] = []
    
    # Regex to capture the line range information from a diff hunk header
    # Group 1: new_start_line, Group 2: new_line_count (optional)
    hunk_header_re = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')

    for line in diff_text.split('\n'):
        # New file in diff (target file)
        if line.startswith('+++ b/'):
            # If we were tracking a previous file, add it to the list
            if current_file:
                files.append({'path': current_file, 'lines': current_lines})
            current_file = line[6:].strip() # Remove '+++ b/' prefix and any trailing whitespace
            current_lines = [] # Reset lines for the new file
        elif current_file and line.startswith('@@'):
            # This is a hunk header, extract new line start and count
            match = hunk_header_re.match(line)
            if match:
                start_line = int(match.group(1))
                # Default count is 1 if not specified (e.g., +1)
                line_count = int(match.group(2)) if match.group(2) else 1 
                
                # Represent the hunk as a single range (start, end)
                # If line_count is 0 (e.g., only deletions in the hunk),
                # we can represent it as a single point or skip.
                # For now, if line_count is 0, we'll make the range (start_line, start_line).
                # This indicates the context of the change, even if no lines were added.
                if line_count > 0:
                    current_lines.append((start_line, start_line + line_count - 1))
                else:
                    current_lines.append((start_line, start_line)) # Represents a point where changes occurred (e.g., deletions)
            
    # Add the last file if any was being tracked
    if current_file:
        files.append({'path': current_file, 'lines': current_lines})
        
    return files
