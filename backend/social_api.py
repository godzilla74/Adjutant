import json

import httpx

from backend.social_oauth import get_valid_access_token

_TWITTER_BASE = "https://api.twitter.com/2"
_LINKEDIN_BASE = "https://api.linkedin.com/v2"
_META_BASE = "https://graph.facebook.com/v19.0"


async def twitter_post(product_id: str, text: str, media_url: str | None = None) -> str:
    token = await get_valid_access_token(product_id, "twitter")
    body: dict = {"text": text}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_TWITTER_BASE}/tweets",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Twitter post error: {e.response.status_code}") from e
        data = resp.json()["data"]
    return json.dumps({
        "posted": True,
        "post_id": data["id"],
        "url": f"https://twitter.com/i/web/status/{data['id']}",
    })


async def linkedin_post(product_id: str, text: str, media_url: str | None = None) -> str:
    token = await get_valid_access_token(product_id, "linkedin")
    from backend.db import get_oauth_connection
    conn = get_oauth_connection(product_id, "linkedin")
    author_urn = conn["email"]  # stored as urn:li:person:{id}
    body = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_LINKEDIN_BASE}/ugcPosts",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"LinkedIn post error: {e.response.status_code}") from e
        data = resp.json()
    post_id = data.get("id", "")
    return json.dumps({"posted": True, "post_id": post_id})


async def facebook_post(product_id: str, text: str, media_url: str | None = None) -> str:
    token = await get_valid_access_token(product_id, "facebook")
    from backend.db import get_oauth_connection
    conn = get_oauth_connection(product_id, "facebook")
    page_id = conn["email"]  # stored as the page ID
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_META_BASE}/{page_id}/feed",
            params={"access_token": token, "message": text},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Facebook post error: {e.response.status_code}") from e
        data = resp.json()
    return json.dumps({"posted": True, "post_id": data.get("id", "")})


async def instagram_post(product_id: str, caption: str, image_url: str) -> str:
    token = await get_valid_access_token(product_id, "instagram")
    from backend.db import get_oauth_connection
    conn = get_oauth_connection(product_id, "instagram")
    ig_id = conn["email"]  # stored as the Instagram business account ID
    async with httpx.AsyncClient() as client:
        container_resp = await client.post(
            f"{_META_BASE}/{ig_id}/media",
            params={"image_url": image_url, "caption": caption, "access_token": token},
        )
        try:
            container_resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Instagram media container error: {e.response.status_code}") from e
        container_id = container_resp.json()["id"]
        publish_resp = await client.post(
            f"{_META_BASE}/{ig_id}/media_publish",
            params={"creation_id": container_id, "access_token": token},
        )
        try:
            publish_resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Instagram publish error: {e.response.status_code}") from e
        data = publish_resp.json()
    return json.dumps({"posted": True, "post_id": data.get("id", "")})
