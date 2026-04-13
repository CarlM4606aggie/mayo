
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

def co_author_msg(msg):
    co_author_name = os.environ.get('CO_AUTHOR_NAME', '')
    co_author_email = os.environ.get('CO_AUTHOR_EMAIL', '')
    if co_author_name and co_author_email:
        return f"{msg}\n\nCo-authored-by: {co_author_name} <{co_author_email}>"
    return msg

# Config
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI2_API_KEY = os.environ.get('GEMINI2_API_KEY')
GROK_API_KEY = os.environ.get('GROK_API_KEY')
GEMINI_FALLBACK_API_KEY = os.environ.get('GEMINI_FALLBACK_API_KEY')
GEMINI2_FALLBACK_API_KEY = os.environ.get('GEMINI2_FALLBACK_API_KEY')
GROK_FALLBACK_API_KEY = os.environ.get('GROK_FALLBACK_API_KEY')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
FIREWORKS_API_KEY = os.environ.get('FIREWORKS_API_KEY')
GEMINI_NEWCRONS_API_KEY = os.environ.get('GEMINI_NEWCRONS_API_KEY')
GROQ_NEWCRONS_API_KEY = os.environ.get('GROQ_NEWCRONS_API_KEY')
APP_ID = os.environ.get('APP_ID')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY', '').replace('\\n', '\n')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET')
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Helper: Verify Webhook Signature
def verify_signature(req):
    signature = req.headers.get('X-Hub-Signature-256')
    if not WEBHOOK_SECRET:
        print("ERROR: WEBHOOK_SECRET is not set in environment variables.")
        return False, "WEBHOOK_SECRET_MISSING"
    if not signature:
        print("ERROR: No X-Hub-Signature-256 header provided.")
        return False, "SIGNATURE_MISSING"
    
    try:
        sha_name, signature_hash = signature.split('=')
    except ValueError:
        return False, "INVALID_SIGNATURE_FORMAT"

    if sha_name != 'sha256':
        return False, "UNSUPPORTED_HASH_ALGORITHM"
    
    mac = hmac.new(WEBHOOK_SECRET.encode('utf-8'), req.data, hashlib.sha256)
    expected = mac.hexdigest()
    if not hmac.compare_digest(expected.encode('utf-8'), signature_hash.encode('utf-8')):
        safe_expected = expected[:8]
        safe_got = signature_hash[:8]
        print(f"ERROR: Signature mismatch. Expected {safe_expected}... but got {safe_got}... (Payload len: {len(req.data)})")
        return False, f"SIGNATURE_MISMATCH (len:{len(req.data)})"
    
    return True, "OK"

# Helper: Get GitHub Client for Installation
def get_installation_token(installation_id):
    integration = GithubIntegration(APP_ID, PRIVATE_KEY)
    return integration.get_access_token(installation_id).token

def get_github_client(installation_id):
    token = get_installation_token(installation_id)
    return Github(token)

# Helper: Get Bot Login
# NOTE: Cache is checked first to avoid redundant API calls on every request
BOT_LOGIN_CACHE = None
def get_bot_login():
    global BOT_LOGIN_CACHE
    if BOT_LOGIN_CACHE:
        return BOT_LOGIN_CACHE
