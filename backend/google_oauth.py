"""Google OAuth 2.0 flow and token management."""

import base64
import json
import urllib.parse
from datetime import datetime, timezone, timedelta

import httpx

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
_GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

REDIRECT_URI = "http://localhost:8000/api/oauth/callback"

_SCOPES: dict[str, list[str]] = {
    "gmail": [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
    ],
    "google_calendar": [
        "https://www.googleapis.com/auth/calendar",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
    ],
}


def build_authorization_url(product_id: str, service: str, client_id: str) -> str:
    if service not in _SCOPES:
        raise ValueError(f"Unknown service: {service}. Must be one of {list(_SCOPES)}")
    state = base64.urlsafe_b64encode(
        json.dumps({"product_id": product_id, "service": service}).encode()
    ).decode().rstrip("=")
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(_SCOPES[service]),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code_for_tokens(code: str, client_id: str, client_secret: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
        })
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        })
        resp.raise_for_status()
        return resp.json()


async def get_user_email(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()["email"]


async def revoke_token(token: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(_GOOGLE_REVOKE_URL, params={"token": token})


async def get_valid_access_token(product_id: str, service: str) -> str:
    """Return a valid access token, refreshing silently if expired."""
    from backend.db import get_oauth_connection, save_oauth_connection, get_agent_config
    row = get_oauth_connection(product_id, service)
    if not row:
        raise ValueError(f"No {service} connection for product '{product_id}'. Connect it in product settings.")

    expiry = datetime.fromisoformat(row["token_expiry"]) if row.get("token_expiry") else None
    now = datetime.now(timezone.utc)
    if expiry and expiry > now + timedelta(seconds=60):
        return row["access_token"]

    config = get_agent_config()
    client_id = config.get("google_oauth_client_id", "")
    client_secret = config.get("google_oauth_client_secret", "")
    if not client_id or not client_secret:
        raise ValueError("Google OAuth credentials not configured. Add them in global settings.")

    token_data = await refresh_access_token(row["refresh_token"], client_id, client_secret)
    new_expiry = (now + timedelta(seconds=token_data.get("expires_in", 3600))).isoformat()
    save_oauth_connection(
        product_id=product_id, service=service, email=row["email"],
        access_token=token_data["access_token"],
        refresh_token=row["refresh_token"],
        token_expiry=new_expiry, scopes=row["scopes"],
    )
    return token_data["access_token"]
