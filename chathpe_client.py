"""
Real ChatHPE API client for the student project.

Credentials are read exclusively from the Flask app config (sourced from .env).
Nothing is written to disk, logged, or stored outside the process memory.

This mirrors the exact API flow used in the parent project's bug_info.py.
"""

import json
import re

import requests
import urllib3
import os

# Suppress SSL warnings — ChatHPE endpoint uses internal HPE certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_MOCK_HOST = os.getenv("BUGZ_HOST", "https://api.chathpe.it.hpe.com")
_API_BASE = f"{_MOCK_HOST}/v2.8"
_SESSION_URL  = f"{_API_BASE}/sessionId_generator"
_PREFS_URL    = f"{_API_BASE}/preferences"
_CHATLITE_URL = f"{_API_BASE}/call/chatlite"


def load_creds_from_config(app_config):
    """
    Extract ChatHPE credentials from the Flask app config object.

    Config keys (all sourced from .env — never hardcoded):
        CHATHPE_CLIENT_ID, CHATHPE_JWT_TOKEN, CHATHPE_USER_ID, CHATHPE_USERNAME

    Returns a dict with keys: client_id, jwt_token, user_id, username.
    Raises ValueError if any required field is missing or malformed.
    """
    creds = {
        "client_id": app_config.get("CHATHPE_CLIENT_ID"),
        "jwt_token":  app_config.get("CHATHPE_JWT_TOKEN"),
        "user_id":    app_config.get("CHATHPE_USER_ID"),
        "username":   app_config.get("CHATHPE_USERNAME"),
    }
    missing = [k for k, v in creds.items() if not v]
    if missing:
        raise ValueError(
            f"Missing ChatHPE credentials in .env: {missing}. "
            "Set CHATHPE_CLIENT_ID, CHATHPE_JWT_TOKEN, CHATHPE_USER_ID, "
            "CHATHPE_USERNAME in the .env file."
        )
    if not creds["jwt_token"].lower().startswith("bearer "):
        raise ValueError(
            "CHATHPE_JWT_TOKEN must start with 'Bearer ' (include the prefix)."
        )
    return creds


def get_session_id(client_id, jwt_token):
    """Obtain a new ChatHPE session ID."""
    headers = {"Client-id": client_id, "Authorization": jwt_token}
    resp = requests.get(_SESSION_URL, headers=headers, timeout=15, verify=False)
    resp.raise_for_status()
    match = re.search(r"sessionId:\s*([\w-]+)", resp.text)
    if not match:
        raise ValueError(
            f"Could not parse sessionId from ChatHPE response: {resp.text[:200]}"
        )
    return match.group(1)


def set_preferences(session_id, client_id, jwt_token, user_id, username):
    """Set user preferences for the ChatHPE session."""
    payload = {
        "agreement": True,
        "chatHPE_bot_data": {
            "appId": "1",
            "sessionId": session_id,
            "userId": user_id,
            "username": username,
        },
        "webScraping": False,
    }
    headers = {
        "Client-id": client_id,
        "Authorization": jwt_token,
        "Content-Type": "application/json",
    }
    resp = requests.post(
        _PREFS_URL, headers=headers, data=json.dumps(payload), timeout=15, verify=False
    )
    resp.raise_for_status()


def call_chatlite(session_id, prompt, client_id, jwt_token, user_id, username):
    """
    Send a prompt to ChatHPE and return the response text string.

    Uses gpt-4o-mini, stream=False, no web scraping — consistent with
    the parent project's bug_info.py implementation.
    """
    payload = {
        "chatHPE_bot_data": {
            "appId": "1",
            "sessionId": session_id,
            "userId": user_id,
            "username": username,
        },
        "prompts_flag": False,
        "stream": False,
        "webScraping": False,
        "user_query": prompt,
        "model_name": "gpt-4o-mini",
        "force_async": False,
    }
    headers = {
        "Client-id": client_id,
        "Authorization": jwt_token,
        "Content-Type": "application/json",
    }
    resp = requests.post(
        _CHATLITE_URL, headers=headers, data=json.dumps(payload), timeout=120, verify=False
    )
    resp.raise_for_status()
    body = resp.json()
    # ChatHPE returns either {"message": "..."} or {"Response": "..."}
    return body.get("message") or body.get("Response") or ""
