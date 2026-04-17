"""GitHub webhook event handler for mayo.

Handles incoming GitHub webhook events such as pull request reviews,
issue comments, and push events to trigger AI-assisted workflows.
"""

import json
import logging
from typing import Any

from github import Github, GithubException

logger = logging.getLogger(__name__)

# Commands I personally use most often - added /help as a convenience alias for /review
# Also added /check as an alias for /review since I keep typing it by habit
RECOGNIZED_COMMANDS = {
    "/review": "review",
    "/execute": "execute",
    "/help": "review",  # personal alias: /help triggers the same flow as /review
    "/check": "review",  # personal alias: /check also triggers review
    "/lgtm": "review",  # added: /lgtm is another one I find myself typing
}


def handle_pull_request_event(payload: dict, github_client: Github) -> dict:
    """Handle pull_request webhook events.

    Args:
        payload: The webhook payload from GitHub.
        github_client: Authenticated GitHub client instance.

    Returns:
        A dict with status and message describing the action taken.
    """
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    repo_name = payload["repository"]["full_name"]

    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "skipped", "reason": f"Unhandled PR action: {action}"}

    try:
        repo = github_client.get_repo(repo_name)
        pull = repo.get_pull(pr["number"])
        logger.info("Processing PR #%d in %s (action: %s)", pr["number"], repo_name, action)
        return {
            "status": "processed",
            "pr_number": pr["number"],
            "action": action,
            "repo": repo_name,
        }
    except GithubException as exc:
        logger.error("GitHub API error while handling PR event: %s", exc)
        return {"status": "error", "message": str(exc)}


def handle_issue_comment_event(payload: dict, github_client: Github) -> dict:
    """Handle issue_comment webhook events.

    Triggers reviewer or executor flows when specific commands are detected
    in pull request comments (e.g. '/review', '/execute', '/help', '/check', '/lgtm').

    Args:
        payload: The webhook payload from GitHub.
        github_client: Authenticated GitHub client instance.

    Returns:
        A dict with status and message describing the action taken.
    """
    action = payload.get("action")
    if action != "created":
        return {"status": "skipped", "reason": "Only 'created' comments are handled"}

    comment_body = payload.get("comment", {}).get("body", "").strip()
    repo_name = payload["repository"]["full_name"]
    issue_number = payload["issue"]["number"]
    is_pull_request = "pull_request" in payload.get("issue", {})

    if not is_pull_request:
        return {"status": "skipped", "reason": "Comment is not on a pull request"}

    command = None
    # Match commands case-insensitively so '/Review' and '/REVIEW' also work
    comment_lower = comment_body.lower()
    for prefix, cmd in RECOGNIZED_COMMANDS.items():
        if comment_lower.startswith(prefix):
            command = cmd
            break

    if command is None:
        return {"status": "skipped", "reason": "No recognized command found in comment"}

    return {
        "status": "processed",
        "command": command,
        "issue_number": issue_number,
        "repo": repo_name,
    }
