# extensions/social_setup.py
"""Social media presence setup tool.

Workflow:
  1. Research best platforms for the product's demographics (if not specified)
  2. Draft profile content (username, display name, bio) for each platform
  3. Open a VISIBLE browser and fill signup forms
  4. Stop at verification steps → create review items for manual completion
  5. Update product's social_handles brand config
"""

import json
import re
import secrets
import string

TOOL_DEFINITION = {
    "name": "setup_social_media",
    "description": (
        "Set up social media profiles for a product launch. "
        "Researches best platforms for the product's audience, drafts optimized profile content, "
        "opens a visible browser to fill signup forms, stops at verification steps and creates "
        "review items for manual completion, then saves the handles to the product's brand config. "
        "Takes 5-15 minutes — informs Justin upfront. "
        "Requires browser-use to be installed (pip install browser-use langchain-anthropic && playwright install chromium)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "product_id": {
                "type": "string",
                "description": "Product to create accounts for",
            },
            "email": {
                "type": "string",
                "description": "Email address to use when signing up",
            },
            "password": {
                "type": "string",
                "description": "Password to use for new accounts (use a strong unique one). If omitted, a random password is generated.",
            },
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Platforms to set up, e.g. ['instagram', 'tiktok']. "
                    "If omitted, Hannah researches and recommends the best 2-3 based on demographics."
                ),
            },
            "context": {
                "type": "string",
                "description": "Additional context about the product, launch, or target audience",
            },
        },
        "required": ["product_id", "email"],
    },
}

SUPPORTED_PLATFORMS = {
    "instagram": "https://www.instagram.com/accounts/emailsignup/",
    "twitter":   "https://twitter.com/i/flow/signup",
    "linkedin":  "https://www.linkedin.com/signup",
    "tiktok":    "https://www.tiktok.com/signup/phone-or-email/email",
    "facebook":  "https://www.facebook.com/reg/",
    "pinterest": "https://www.pinterest.com/",
}


def _gen_password(length: int = 20) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(chars) for _ in range(length))


async def execute(inputs: dict) -> str:
    product_id = inputs["product_id"]
    email      = inputs["email"]
    password   = inputs.get("password") or _gen_password()
    platforms  = [p.lower() for p in (inputs.get("platforms") or [])]
    context    = inputs.get("context", "")

    from backend.db import get_product_config, update_product, save_review_item
    from agents.runner import run_research_agent, run_general_agent

    config = get_product_config(product_id)
    if not config:
        return json.dumps({"error": f"Product '{product_id}' not found."})

    product_name    = config["name"]
    target_audience = config.get("target_audience") or ""
    brand_voice     = config.get("brand_voice") or ""

    # ── Step 1: Research platforms if not specified ───────────────────────────
    if not platforms:
        research_result = await run_research_agent(_research_prompt(product_name, target_audience, context, config))
        platforms = _parse_platforms(research_result)
        if not platforms:
            return json.dumps({"error": "Could not determine platforms from research. Specify them explicitly."})

    # Filter to supported only
    unsupported = [p for p in platforms if p not in SUPPORTED_PLATFORMS]
    platforms   = [p for p in platforms if p in SUPPORTED_PLATFORMS]
    if not platforms:
        return json.dumps({
            "error": f"None of the requested platforms are supported.",
            "unsupported": unsupported,
            "supported": list(SUPPORTED_PLATFORMS.keys()),
        })

    # ── Step 2: Draft profile content for each platform ───────────────────────
    drafts_raw = await run_general_agent(_drafts_prompt(product_name, platforms, config, context))
    profiles   = _parse_profiles(drafts_raw, platforms, product_name)

    # ── Step 3: Browser signup per platform ───────────────────────────────────
    from extensions.browser_task import execute as run_browser

    results            = []
    handles_acquired: dict = {}

    # Load existing handles
    existing_handles: dict = {}
    try:
        existing_handles = json.loads(config.get("social_handles") or "{}")
    except Exception:
        pass

    for platform in platforms:
        profile      = profiles.get(platform, {})
        username     = profile.get("username", product_name.lower().replace(" ", ""))
        display_name = profile.get("display_name", product_name)
        bio          = profile.get("bio", f"Official {product_name} account.")

        task = _signup_task(platform, email, password, username, display_name, bio, product_name)

        browser_result_raw = await run_browser({
            "task": task,
            "sensitive_data": {"email": email, "password": password},
            "max_steps": 35,
        })
        browser_result = json.loads(browser_result_raw)
        status = browser_result.get("status", "error")
        detail = browser_result.get("result", "")

        if status == "success":
            handles_acquired[platform] = f"@{username}"
            results.append({"platform": platform, "status": "success", "handle": f"@{username}"})

        elif status == "needs_verification":
            # Create a review item the user can tick off after verifying
            review_description = _verification_review(platform, email, username, display_name, bio, detail)
            save_review_item(
                product_id=product_id,
                title=f"Complete {platform.capitalize()} signup — verify your email/phone",
                description=review_description,
                risk_label=f"Manual step required · {platform} · browser left open",
            )
            # Optimistically record the handle (will be confirmed on approval)
            handles_acquired[platform] = f"@{username}"
            results.append({
                "platform": platform,
                "status": "needs_verification",
                "handle": f"@{username}",
                "review_item_created": True,
            })

        else:
            results.append({"platform": platform, "status": status, "error": detail[:300]})

    # ── Step 4: Save handles to brand config ──────────────────────────────────
    if handles_acquired:
        existing_handles.update(handles_acquired)
        update_product(product_id, social_handles=json.dumps(existing_handles))

    # Build summary
    success_count  = sum(1 for r in results if r["status"] == "success")
    verify_count   = sum(1 for r in results if r["status"] == "needs_verification")
    failed_count   = sum(1 for r in results if r["status"] not in ("success", "needs_verification"))

    summary_parts = []
    if success_count:
        summary_parts.append(f"{success_count} created successfully")
    if verify_count:
        summary_parts.append(f"{verify_count} waiting for manual verification (review items created)")
    if failed_count:
        summary_parts.append(f"{failed_count} failed")

    return json.dumps({
        "platforms": platforms,
        "profiles_drafted": profiles,
        "results": results,
        "handles_saved": handles_acquired,
        "password_used": password,  # Return so Justin can save it
        "summary": " · ".join(summary_parts) or "No results.",
        "next_steps": (
            "Check the review queue for any platforms that need email/phone verification. "
            "After verifying, tell Hannah to finalize setup."
        ) if verify_count else None,
    }, indent=2)


# ── Prompt builders ───────────────────────────────────────────────────────────

def _research_prompt(product_name: str, target_audience: str, context: str, config: dict) -> str:
    brand_notes = config.get("brand_notes") or ""
    return f"""Research the best social media platforms for "{product_name}".

Product details:
- Target audience: {target_audience or "not specified"}
- Additional context: {context or "none"}
- Brand notes: {brand_notes or "none"}

Recommend the top 2-3 platforms where this audience is most active and where this type of product gets the best organic reach.
Consider B2B vs B2C fit, content format, and demographic match.

Return ONLY a JSON array of platform names (lowercase), chosen from:
instagram, twitter, linkedin, tiktok, facebook, pinterest

Example: ["linkedin", "instagram"]

No explanation, just the JSON array."""


def _drafts_prompt(product_name: str, platforms: list, config: dict, context: str) -> str:
    brand_ctx = ""
    if config.get("brand_voice"):
        brand_ctx += f"\nBrand voice: {config['brand_voice']}"
    if config.get("tone"):
        brand_ctx += f"\nTone: {config['tone']}"
    if config.get("target_audience"):
        brand_ctx += f"\nTarget audience: {config['target_audience']}"

    platform_limits = {
        "instagram": "Bio: max 150 chars. Casual/visual tone, 1-2 emojis.",
        "twitter":   "Bio: max 160 chars. Punchy and direct.",
        "linkedin":  "Bio: 2-3 professional sentences, max 300 chars. Value-proposition focused.",
        "tiktok":    "Bio: max 80 chars. Energetic, include CTA.",
        "facebook":  "Bio: 1-2 sentences, max 255 chars.",
        "pinterest": "Bio: 1-2 sentences, max 160 chars. Inspirational/visual tone.",
    }
    notes = "\n".join(f"- {p}: {platform_limits.get(p, 'appropriate for platform')}" for p in platforms)

    username_rules = {
        "instagram": "letters, numbers, periods, underscores. 1-30 chars.",
        "twitter":   "letters, numbers, underscores only. 4-15 chars.",
        "linkedin":  "letters, numbers, hyphens. 3-100 chars (URL slug).",
        "tiktok":    "letters, numbers, underscores, periods. 2-24 chars.",
        "facebook":  "letters, numbers, periods. 5-50 chars.",
        "pinterest": "letters, numbers, underscores. 3-30 chars.",
    }
    username_notes = "\n".join(f"- {p}: {username_rules.get(p, 'standard rules')}" for p in platforms)

    return f"""Draft social media profile content for "{product_name}" on: {", ".join(platforms)}.
{brand_ctx}
Context: {context or "product launch"}

Platform-specific bio guidelines:
{notes}

Username rules per platform:
{username_notes}

For each platform, provide:
- username: memorable handle derived from the product name, no spaces, all lowercase
- display_name: shown name (can have spaces, e.g. "RetainerOps")
- bio: platform-appropriate bio within character limits

Return ONLY valid JSON:
{{
  "instagram": {{"username": "...", "display_name": "...", "bio": "..."}},
  "twitter":   {{"username": "...", "display_name": "...", "bio": "..."}},
  ...
}}"""


def _signup_task(
    platform: str, email: str, password: str,
    username: str, display_name: str, bio: str, product_name: str,
) -> str:
    signup_url = SUPPORTED_PLATFORMS[platform]

    username_fallbacks = f"{username}hq, {username}app, {username}official, get{username}"

    base = f"""Create a new {platform.capitalize()} account for the product "{product_name}".

Go to: {signup_url}

Use these credentials (injected securely as {{email}} and {{password}}):
- Email: {{email}}
- Password: {{password}}
- Username / handle: {username}
  (If taken, try in order: {username_fallbacks})
- Display name: {display_name}

CRITICAL RULES — follow exactly:
1. Fill in ALL required fields on each page before clicking Next/Continue/Sign Up.
2. If a username is already taken, try the fallbacks listed above in order.
3. STOP IMMEDIATELY and output "VERIFICATION_REQUIRED" when you encounter ANY of:
   - A field asking for a phone number (with no visible skip option)
   - An email verification code input
   - A CAPTCHA / "I'm not a robot" challenge
   - An SMS code input
   - "Confirm you're human"
4. If there IS a visible "Skip" link on the phone step, click Skip and continue.
5. Do NOT enter a real phone number. Do NOT try to solve CAPTCHAs.
6. After successfully creating the account (before verification wall), navigate to
   profile/bio settings and add this bio: {bio}

When you stop at a verification wall, output:
"VERIFICATION_REQUIRED: [describe what's on screen]. Username used: {username}. Reached step: [step name]."

When the account is fully created with no wall, output:
"SUCCESS: Account created. Username: [actual username secured]. Profile URL: [url if shown]."
"""
    return base


# ── Post-signup review item description ───────────────────────────────────────

def _verification_review(
    platform: str, email: str, username: str,
    display_name: str, bio: str, agent_detail: str,
) -> str:
    return f"""**Platform:** {platform.capitalize()}
**Status:** Stopped at verification step

**What the browser agent reported:**
{agent_detail[:500] if agent_detail else "Reached verification screen."}

---

**To complete this signup:**
1. The browser window should still be open at the {platform.capitalize()} verification page.
   If it closed, go to: {SUPPORTED_PLATFORMS[platform]}
2. Log in / resume with **{email}**
3. Complete the verification (check your email or phone for a code)
4. Once in, update your profile:
   - Username: `{username}`
   - Display name: `{display_name}`
   - Bio: {bio}

**Mark as Approved** once the account is live."""


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_platforms(research_text: str) -> list[str]:
    match = re.search(r'\[([^\]]+)\]', research_text)
    if match:
        try:
            raw = json.loads(f"[{match.group(1)}]")
            return [p.lower().strip() for p in raw if isinstance(p, str) and p.lower().strip() in SUPPORTED_PLATFORMS][:3]
        except Exception:
            pass
    # Fallback: scan for known names
    found = []
    for p in SUPPORTED_PLATFORMS:
        if re.search(r'\b' + p + r'\b', research_text.lower()) and p not in found:
            found.append(p)
    return found[:3]


def _parse_profiles(raw: str, platforms: list, product_name: str) -> dict:
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            parsed = json.loads(match.group(0))
            result = {}
            for p in platforms:
                if p in parsed and isinstance(parsed[p], dict):
                    result[p] = {
                        "username":     str(parsed[p].get("username", _slug(product_name))),
                        "display_name": str(parsed[p].get("display_name", product_name)),
                        "bio":          str(parsed[p].get("bio", f"Official {product_name} account.")),
                    }
            # Fill in any missing platforms
            for p in platforms:
                if p not in result:
                    result[p] = _fallback_profile(p, product_name)
            return result
        except Exception:
            pass
    return {p: _fallback_profile(p, product_name) for p in platforms}


def _fallback_profile(platform: str, product_name: str) -> dict:
    return {
        "username":     _slug(product_name),
        "display_name": product_name,
        "bio":          f"Official {product_name} account.",
    }


def _slug(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', name.lower())[:20]
