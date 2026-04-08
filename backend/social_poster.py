# backend/social_poster.py
"""Social media posting backends for Adjutant.

Credentials are loaded from environment variables:

  Twitter/X:
    TWITTER_API_KEY
    TWITTER_API_SECRET
    TWITTER_ACCESS_TOKEN
    TWITTER_ACCESS_TOKEN_SECRET

  LinkedIn:
    LINKEDIN_ACCESS_TOKEN
    LINKEDIN_AUTHOR_URN   (e.g. urn:li:person:XXXXXXXX)
                          Retrieve with: GET https://api.linkedin.com/v2/me

  Facebook:
    FACEBOOK_PAGE_ACCESS_TOKEN
    FACEBOOK_PAGE_ID

  Instagram:  (requires a Meta Business/Creator account linked to a Facebook Page)
    META_ACCESS_TOKEN
    INSTAGRAM_BUSINESS_ACCOUNT_ID
"""
import base64
import hashlib
import hmac
import os
import time
import uuid
from urllib.parse import quote

import httpx


def _env(key: str) -> str | None:
    return os.environ.get(key)


# ── Twitter/X ─────────────────────────────────────────────────────────────────

def _twitter_oauth_header(method: str, url: str) -> str | None:
    api_key   = _env("TWITTER_API_KEY")
    api_sec   = _env("TWITTER_API_SECRET")
    at        = _env("TWITTER_ACCESS_TOKEN")
    at_sec    = _env("TWITTER_ACCESS_TOKEN_SECRET")
    if not all([api_key, api_sec, at, at_sec]):
        return None

    oauth = {
        "oauth_consumer_key":     api_key,
        "oauth_nonce":            uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        str(int(time.time())),
        "oauth_token":            at,
        "oauth_version":          "1.0",
    }
    params_str = "&".join(
        f"{quote(k, safe='')}={quote(v, safe='')}"
        for k, v in sorted(oauth.items())
    )
    base = "&".join([method.upper(), quote(url, safe=""), quote(params_str, safe="")])
    key  = f"{quote(api_sec, safe='')}&{quote(at_sec, safe='')}"
    sig  = base64.b64encode(
        hmac.new(key.encode(), base.encode(), digestmod=hashlib.sha1).digest()
    ).decode()
    oauth["oauth_signature"] = sig
    return "OAuth " + ", ".join(
        f'{quote(k, safe="")}="{quote(v, safe="")}"'
        for k, v in sorted(oauth.items())
    )


async def post_to_twitter(content: str) -> dict:
    url  = "https://api.twitter.com/2/tweets"
    auth = _twitter_oauth_header("POST", url)
    if auth is None:
        return {
            "success": False,
            "error": (
                "Twitter credentials not configured. "
                "Add TWITTER_API_KEY, TWITTER_API_SECRET, "
                "TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET to .env"
            ),
        }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            headers={"Authorization": auth, "Content-Type": "application/json"},
            json={"text": content},
        )
    if resp.status_code in (200, 201):
        tweet_id = resp.json().get("data", {}).get("id", "")
        return {
            "success": True,
            "post_url": f"https://twitter.com/i/web/status/{tweet_id}",
            "post_id": tweet_id,
        }
    return {"success": False, "error": f"Twitter API {resp.status_code}: {resp.text[:400]}"}


# ── LinkedIn ──────────────────────────────────────────────────────────────────

async def post_to_linkedin(content: str) -> dict:
    token      = _env("LINKEDIN_ACCESS_TOKEN")
    author_urn = _env("LINKEDIN_AUTHOR_URN")
    if not token or not author_urn:
        return {
            "success": False,
            "error": (
                "LinkedIn credentials not configured. "
                "Add LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN to .env"
            ),
        }
    body = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": content},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json=body,
        )
    if resp.status_code in (200, 201):
        post_id = resp.headers.get("x-restli-id", "")
        post_url = (
            f"https://www.linkedin.com/feed/update/{post_id}"
            if post_id else "https://www.linkedin.com/feed/"
        )
        return {"success": True, "post_url": post_url, "post_id": post_id}
    return {"success": False, "error": f"LinkedIn API {resp.status_code}: {resp.text[:400]}"}


# ── Facebook ──────────────────────────────────────────────────────────────────

async def post_to_facebook(content: str) -> dict:
    page_token = _env("FACEBOOK_PAGE_ACCESS_TOKEN")
    page_id    = _env("FACEBOOK_PAGE_ID")
    if not page_token or not page_id:
        return {
            "success": False,
            "error": (
                "Facebook credentials not configured. "
                "Add FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_PAGE_ID to .env"
            ),
        }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://graph.facebook.com/v19.0/{page_id}/feed",
            params={"access_token": page_token},
            json={"message": content},
        )
    if resp.status_code == 200:
        post_id = resp.json().get("id", "")
        return {
            "success": True,
            "post_url": f"https://www.facebook.com/{post_id}",
            "post_id": post_id,
        }
    return {"success": False, "error": f"Facebook API {resp.status_code}: {resp.text[:400]}"}


# ── Instagram ─────────────────────────────────────────────────────────────────

async def post_to_instagram(content: str, image_url: str = "") -> dict:
    access_token = _env("META_ACCESS_TOKEN")
    account_id   = _env("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    if not access_token or not account_id:
        return {
            "success": False,
            "error": (
                "Instagram credentials not configured. "
                "Add META_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ACCOUNT_ID to .env"
            ),
        }
    if not image_url:
        return {
            "success": False,
            "error": (
                "Instagram requires a public image URL. "
                "Provide image_url when drafting the post."
            ),
        }
    base   = f"https://graph.facebook.com/v19.0/{account_id}"
    params = {"access_token": access_token}

    async with httpx.AsyncClient(timeout=20) as client:
        # Step 1: Create media container
        r1 = await client.post(
            f"{base}/media",
            params={**params, "image_url": image_url, "caption": content},
        )
        if r1.status_code != 200:
            return {"success": False, "error": f"Instagram media container error {r1.status_code}: {r1.text[:400]}"}
        creation_id = r1.json().get("id")

        # Step 2: Publish
        r2 = await client.post(
            f"{base}/media_publish",
            params={**params, "creation_id": creation_id},
        )
        if r2.status_code != 200:
            return {"success": False, "error": f"Instagram publish error {r2.status_code}: {r2.text[:400]}"}
        media_id = r2.json().get("id", "")

    return {
        "success": True,
        "post_url": f"https://www.instagram.com/p/{media_id}/",
        "post_id": media_id,
    }


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def publish_social_draft(draft: dict) -> dict:
    """Dispatch to the correct platform poster.

    Args:
        draft: A social_drafts row dict with at least 'platform', 'content', 'image_url'.

    Returns:
        dict with keys: success (bool), post_url (str, optional), error (str, optional)
    """
    platform  = (draft.get("platform") or "").lower().strip()
    content   = draft.get("content", "")
    image_url = draft.get("image_url", "") or ""

    if platform in ("twitter", "x"):
        return await post_to_twitter(content)
    if platform == "linkedin":
        return await post_to_linkedin(content)
    if platform == "facebook":
        return await post_to_facebook(content)
    if platform == "instagram":
        return await post_to_instagram(content, image_url)

    return {
        "success": False,
        "error": f"Unknown platform '{platform}'. Supported: twitter, linkedin, facebook, instagram.",
    }
