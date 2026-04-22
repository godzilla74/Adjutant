import base64
import hashlib
import os
import secrets
import urllib.parse

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
TOKEN_URL = "https://auth.openai.com/oauth/token"
_AUTH_URL = "https://auth.openai.com/oauth/authorize"
_SCOPES = "openid profile email offline_access api.connectors.read api.connectors.invoke"
_PORT = os.environ.get("HANNAH_PORT", "8001")
REDIRECT_URI = f"http://localhost:{_PORT}/api/openai-oauth/callback"

_pending_verifier: str | None = None


def build_auth_url() -> str:
    """Generate PKCE auth URL and store verifier for later exchange."""
    global _pending_verifier
    raw = secrets.token_bytes(32)
    verifier = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    _pending_verifier = verifier
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": _SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"


def pop_verifier() -> str | None:
    """Return and clear the pending PKCE verifier."""
    global _pending_verifier
    v = _pending_verifier
    _pending_verifier = None
    return v
