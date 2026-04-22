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

# Maps state → code_verifier for pending OAuth flows
_pending: dict[str, str] = {}


def build_auth_url() -> str:
    """Generate PKCE auth URL with state parameter and store verifier."""
    raw = secrets.token_bytes(32)
    verifier = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    _pending[state] = verifier
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": _SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"


def pop_verifier(state: str) -> str | None:
    """Return and remove the verifier for the given state, or None if not found."""
    return _pending.pop(state, None)
