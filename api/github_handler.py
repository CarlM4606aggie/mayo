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
RECOGNIZED_COMMANDS = {
    "/review": "review",
    "/execute": "execute",
    "/help": "review",  # personal alias: /help triggers the same flow as /review
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
    in pull request comments (e.g. '/review', '/execute', '/help').

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
    for prefix, cmd in RECOGNIZED_COMMANDS.items():
        if comment_body.startswith(prefix):
            command = cmd
            break

    if command is None:
        return {"status": "skipped", "reason": "No recognized command in comment"}

    try:
        repo = github_client.get_repo(repo_name)
        pull = repo.get_pull(issue_number)
        logger.info(
            "Command '/%s' triggered on PR #%d in %s",
            command,
            issue_number,
            repo_name,
        )
        return {
            "status": "triggered",
