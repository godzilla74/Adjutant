import base64
import hashlib
import json
import logging
import os
import secrets

import httpx

log = logging.getLogger(__name__)

_PORT = os.environ.get("HANNAH_PORT", "8001")
REDIRECT_URI = f"http://localhost:{_PORT}/api/oauth/callback"

_TWITTER_AUTH_URL = "https://twitter.com/i/oauth2/authorize"
_TWITTER_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
_TWITTER_USER_URL = "https://api.twitter.com/2/users/me"
_TWITTER_REVOKE_URL = "https://api.twitter.com/2/oauth2/revoke"

_LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
_LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
_LINKEDIN_USER_URL = "https://api.linkedin.com/v2/userinfo"  # OpenID Connect endpoint

_META_AUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
_META_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
_META_PAGES_URL = "https://graph.facebook.com/v19.0/me/accounts"

_SCOPES = {
    "twitter":  "tweet.write tweet.read users.read offline.access",
    "linkedin": "openid profile email w_member_social",
    "meta":     "pages_show_list,pages_manage_posts,pages_read_engagement,instagram_basic,instagram_content_publish",
}

# Twitter PKCE: state → code_verifier (in-memory, single-server)
_pkce_store: dict[str, str] = {}


def _make_state(product_id: str, service: str) -> str:
    payload = json.dumps({"product_id": product_id, "service": service})
    return base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()


def build_authorization_url(product_id: str, service: str, client_id: str) -> str:
    if service not in _SCOPES:
        raise ValueError(f"Unknown service: {service}")
    state = _make_state(product_id, service)
    if service == "twitter":
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        _pkce_store[state] = code_verifier
        params = (
            f"?response_type=code&client_id={client_id}"
            f"&redirect_uri={REDIRECT_URI}&scope={_SCOPES['twitter'].replace(' ', '%20')}"
            f"&state={state}&code_challenge={code_challenge}&code_challenge_method=S256"
        )
        return _TWITTER_AUTH_URL + params
    if service == "linkedin":
        params = (
            f"?response_type=code&client_id={client_id}"
            f"&redirect_uri={REDIRECT_URI}&scope={_SCOPES['linkedin'].replace(' ', '%20')}"
            f"&state={state}"
        )
        return _LINKEDIN_AUTH_URL + params
    if service == "meta":
        params = (
            f"?client_id={client_id}&redirect_uri={REDIRECT_URI}"
            f"&scope={_SCOPES['meta']}&state={state}&response_type=code"
        )
        return _META_AUTH_URL + params
    raise ValueError(f"Unknown service: {service}")


async def exchange_code_for_tokens(
    code: str, service: str, client_id: str, client_secret: str,
    code_verifier: str | None = None, state: str | None = None,
) -> dict:
    if service == "twitter":
        verifier = code_verifier or (state and _pkce_store.pop(state, None))
        if not verifier:
            raise RuntimeError("Twitter PKCE code_verifier not found")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _TWITTER_TOKEN_URL,
                data={
                    "code": code, "grant_type": "authorization_code",
                    "client_id": client_id, "redirect_uri": REDIRECT_URI,
                    "code_verifier": verifier,
                },
                auth=(client_id, client_secret),
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Twitter token exchange error: {e.response.status_code}") from e
        return resp.json()
    if service == "linkedin":
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _LINKEDIN_TOKEN_URL,
                data={
                    "grant_type": "authorization_code", "code": code,
                    "redirect_uri": REDIRECT_URI, "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"LinkedIn token exchange error: {e.response.status_code}") from e
        return resp.json()
    if service == "meta":
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _META_TOKEN_URL,
                params={
                    "client_id": client_id, "redirect_uri": REDIRECT_URI,
                    "client_secret": client_secret, "code": code,
                },
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Meta token exchange error: {e.response.status_code}") from e
        return resp.json()
    raise ValueError(f"Unknown service: {service}")


async def refresh_twitter_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _TWITTER_TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id},
            auth=(client_id, client_secret),
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Twitter token refresh error: {e.response.status_code}") from e
    return resp.json()


async def get_twitter_username(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _TWITTER_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Twitter user fetch error: {e.response.status_code}") from e
    return "@" + resp.json()["data"]["username"]


async def get_linkedin_urn(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _LINKEDIN_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"LinkedIn user fetch error: {e.response.status_code}") from e
    data = resp.json()
    # OpenID Connect userinfo returns 'sub' as the person URN
    sub = data.get("sub") or data.get("id", "")
    return f"urn:li:person:{sub}"


async def get_meta_assets(access_token: str) -> tuple[list[dict], str]:
    """Return (assets, debug_info). assets: [{service, account_id, access_token, name}, ...]"""
    assets = []
    debug_parts: list[str] = []
    async with httpx.AsyncClient() as client:
        perms_resp = await client.get(
            "https://graph.facebook.com/v19.0/me/permissions",
            params={"access_token": access_token},
        )
        perms = [p["permission"] for p in perms_resp.json().get("data", []) if p.get("status") == "granted"]
        debug_parts.append(f"granted_perms={perms}")

        # Path 1: personal pages via /me/accounts
        resp = await client.get(
            _META_PAGES_URL,
            params={"fields": "id,name,access_token,instagram_business_account", "access_token": access_token},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Meta pages fetch error: {e.response.status_code}: {e.response.text}") from e
        pages = resp.json().get("data", [])
        debug_parts.append(f"me/accounts={len(pages)} pages")

        # Path 2: business-portfolio-owned pages via /me/businesses (for Business accounts)
        if not pages:
            biz_resp = await client.get(
                "https://graph.facebook.com/v19.0/me/businesses",
                params={"fields": "id,name", "access_token": access_token},
            )
            businesses = biz_resp.json().get("data", [])
            debug_parts.append(f"me/businesses={[b['name'] for b in businesses]}")
            for biz in businesses:
                owned_resp = await client.get(
                    f"https://graph.facebook.com/v19.0/{biz['id']}/owned_pages",
                    params={"fields": "id,name,access_token,instagram_business_account", "access_token": access_token},
                )
                biz_pages = owned_resp.json().get("data", [])
                debug_parts.append(f"biz {biz['name']} owned_pages={len(biz_pages)}")
                pages.extend(biz_pages)

        for page in pages:
            page_token = page.get("access_token", access_token)
            assets.append({
                "service": "facebook",
                "account_id": page["id"],
                "access_token": page_token,
                "name": page.get("name", page["id"]),
            })
            ig = page.get("instagram_business_account")
            if ig:
                ig_resp = await client.get(
                    f"https://graph.facebook.com/v19.0/{ig['id']}",
                    params={"fields": "username", "access_token": page_token},
                )
                ig_username = ig_resp.json().get("username", ig["id"]) if ig_resp.is_success else ig["id"]
                assets.append({
                    "service": "instagram",
                    "account_id": ig["id"],
                    "access_token": page_token,
                    "name": f"@{ig_username}",
                })

    return assets, " | ".join(debug_parts)


async def revoke_social_token(access_token: str, service: str) -> None:
    if service == "twitter":
        async with httpx.AsyncClient() as client:
            await client.post(
                _TWITTER_REVOKE_URL,
                data={"token": access_token, "token_type_hint": "access_token"},
            )


async def get_valid_access_token(product_id: str, service: str) -> str:
    from datetime import datetime, timezone, timedelta
    from backend.db import get_oauth_connection, save_oauth_connection, get_agent_config

    conn = get_oauth_connection(product_id, service)
    if not conn:
        raise RuntimeError(
            f"No {service} connection for product {product_id}. "
            "Connect the account in Settings → Connections."
        )

    if conn["token_expiry"]:
        expiry = datetime.fromisoformat(conn["token_expiry"])
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry - datetime.now(timezone.utc) > timedelta(seconds=60):
            return conn["access_token"]
    else:
        # No expiry recorded — treat token as valid
        return conn["access_token"]

    # LinkedIn: no refresh token — raise to notify user
    if service == "linkedin":
        raise RuntimeError(
            "LinkedIn access token expired. Please reconnect LinkedIn in Settings → Connections."
        )

    # Twitter: refresh via refresh token
    if service == "twitter":
        config = get_agent_config()
        token_data = await refresh_twitter_token(
            conn["refresh_token"],
            config["twitter_client_id"],
            config["twitter_client_secret"],
        )
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 7200))).isoformat()
        save_oauth_connection(
            product_id=product_id, service=service, email=conn["email"],
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", conn["refresh_token"]),
            token_expiry=expiry, scopes=conn["scopes"],
        )
        return token_data["access_token"]

    # Facebook / Instagram: page tokens are long-lived — if expired, user must reconnect
    raise RuntimeError(
        f"{service} token expired. Please reconnect in Settings → Connections."
    )
