
import os
import json
import re
import requests
import hmac
import hashlib
import time
from flask import Flask, request, jsonify
from github import Github, GithubIntegration

app = Flask(__name__)

# Config
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
APP_ID = os.environ.get('APP_ID')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY', '').replace('\\n', '\n')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET')
# GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Helper: Verify Webhook Signature
def verify_signature(req):
    signature = req.headers.get('X-Hub-Signature-256')
    if not signature or not WEBHOOK_SECRET:
        return False
    
    sha_name, signature = signature.split('=')
    if sha_name != 'sha256':
        return False
    
    mac = hmac.new(WEBHOOK_SECRET.encode(), req.data, hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

# Helper: Get GitHub Client for Installation
def get_installation_token(installation_id):
    integration = GithubIntegration(APP_ID, PRIVATE_KEY)
    return integration.get_access_token(installation_id).token

def get_github_client(installation_id):
    token = get_installation_token(installation_id)
    return Github(token)

# Helper: Get Bot Login
BOT_LOGIN_CACHE = None
def get_bot_login():
    global BOT_LOGIN_CACHE
    if BOT_LOGIN_CACHE:
        return BOT_LOGIN_CACHE
    try:
        integration = GithubIntegration(APP_ID, PRIVATE_KEY)
        BOT_LOGIN_CACHE = f"{integration.get_app().slug}[bot]"
        return BOT_LOGIN_CACHE
    except Exception as e:
        print(f"Error getting bot login: {e}")
        return "joe-gemini-bot[bot]"



def fetch_memory(repo, issue_number, bot_login):
    """Read bot's previous comments and extract [MEMORY] blocks."""
    try:
        issue = repo.get_issue(number=issue_number)
        memory_data = {
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
                        if 'files_read' in mem:
                            memory_data['files_read'].extend(mem['files_read'])
                        if 'context_summary' in mem:
                            memory_data['context_summary'] = mem['context_summary']
                    except json.JSONDecodeError:
                        pass
        
        # Deduplicate files
        memory_data['files_read'] = list(set(memory_data['files_read']))
        return memory_data
    except Exception as e:
        print(f"Memory fetch error: {e}")
        return {"files_read": [], "context_summary": ""}

def format_memory_block(data):
    """Format memory data as a hidden HTML comment."""
    return f"\n\n<!-- [MEMORY]{json.dumps(data)}[/MEMORY] -->"

def get_repo_structure(repo, path="", max_depth=1, current_depth=0):
    """Get repository file structure via GitHub API (single level to avoid timeout)."""
    if current_depth > max_depth:
        return ""
    
    structure = ""
    try:
        contents = repo.get_contents(path)
        # Sort: dirs first, then files
        items = sorted(contents, key=lambda x: (x.type != 'dir', x.name))
        
        for item in items[:30]:  # Limit to 30 items to avoid timeout
            if item.name.startswith('.'):
                continue
            
            indent = "  " * current_depth
            marker = "📁 " if item.type == 'dir' else "📄 "
            structure += f"{indent}{marker}{item.name}\n"
            
            # Only go 1 level deep to avoid timeout
            if item.type == 'dir' and current_depth < max_depth:
                structure += get_repo_structure(repo, item.path, max_depth, current_depth + 1)
    except Exception as e:
        print(f"Repo structure error: {e}")
        structure = f"Error: {e}\n"
    
    return structure

def parse_diff_files(diff_text):
    """Parse unified diff to extract changed files with their line ranges."""
    files = []
    current_file = None
    current_lines = []
    new_line_num = 0 # Initialize line number for the new file

    for line in diff_text.split('\n'):
        # New file in diff
        if line.startswith('+++ b/'):
            if current_file:
                # Append lines for the previous file before starting a new one
                files.append({'path': current_file, 'lines': sorted(list(set(current_lines)))})
            current_file = line[6:]  # Remove '+++ b/'
            current_lines = []
            new_line_num = 0 # Reset for new file
        # Hunk header: @@ -old,count +new,count @@
        elif line.startswith('@@') and current_file:
            import re as _re # Keep existing import location for surgical precision
            match = _re.search(r'\+(\d+)(?:,(\d+))?', line)
            if match:
                # Set the starting line number for the current hunk in the new file
                new_line_num = int(match.group(1))
        elif current_file:
            # Process lines within a file
            if line.startswith('+'):
                # Added line
                current_lines.append(new_line_num)
                new_line_num += 1
            elif line.startswith(' '):
                # Context line (unchanged)
                new_line_num += 1
            # Lines starting with '-' are deletions and do not affect new_line_num
    
    # Add the last file's changes if any exist after the loop finishes
    if current_file:
        files.append({'path': current_file, 'lines': sorted(list(set(current_lines)))})
        
    return files