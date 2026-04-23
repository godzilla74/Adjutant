import base64
import hashlib
import http.server
import logging
import secrets
import threading
import urllib.parse

import httpx

logger = logging.getLogger(__name__)

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
TOKEN_URL = "https://auth.openai.com/oauth/token"
_AUTH_URL = "https://auth.openai.com/oauth/authorize"
_SCOPES = "openid profile email offline_access api.connectors.read api.connectors.invoke"
CALLBACK_PORT = 1455
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/auth/callback"

# Maps state → code_verifier for pending OAuth flows
_pending: dict[str, str] = {}

# Running callback server (only one at a time)
_callback_server: http.server.HTTPServer | None = None
_callback_timer: threading.Timer | None = None


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
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
    }
    return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"


def pop_verifier(state: str) -> str | None:
    """Return and remove the verifier for the given state, or None if not found."""
    return _pending.pop(state, None)


def _shutdown_callback_server() -> None:
    global _callback_server, _callback_timer
    if _callback_timer:
        _callback_timer.cancel()
        _callback_timer = None
    if _callback_server:
        try:
            _callback_server.shutdown()
        except Exception:
            pass
        _callback_server = None


def start_callback_server() -> None:
    """Spin up a temporary HTTP server on port 1455 to receive the OAuth callback."""
    global _callback_server, _callback_timer

    _shutdown_callback_server()

    _HTML_DONE = (
        "<html><body><script>setTimeout(()=>window.close(),2000)</script>"
        "<p style='font-family:sans-serif;padding:20px'>Connected! You can close this window.</p>"
        "</body></html>"
    )

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/auth/callback":
                self.send_response(404)
                self.end_headers()
                return

            params = urllib.parse.parse_qs(parsed.query)
            code = (params.get("code") or [None])[0]
            returned_state = (params.get("state") or [None])[0]
            error = (params.get("error") or [None])[0]

            err_msg: str | None = None
            if error or not code:
                err_msg = error or "missing code"
                logger.warning("OpenAI OAuth callback error: %s", err_msg)
            else:
                verifier = pop_verifier(returned_state or "")
                if not verifier:
                    err_msg = "invalid or expired session"
                    logger.warning("OpenAI OAuth: unknown state %r", returned_state)
                else:
                    # Exchange tokens synchronously before responding so the token
                    # is stored before the popup closes and the frontend stops polling.
                    err_msg = _exchange_tokens(code, verifier)

            if err_msg:
                html = (
                    "<html><body style='font-family:sans-serif;padding:20px'>"
                    f"<p style='color:red'>Authentication failed: {err_msg}</p>"
                    "<p>You can close this window.</p></body></html>"
                )
            else:
                html = _HTML_DONE
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

            threading.Thread(target=_shutdown_callback_server, daemon=True).start()

        def log_message(self, *args):
            pass

    try:
        _callback_server = http.server.HTTPServer(("127.0.0.1", CALLBACK_PORT), _Handler)
    except OSError as exc:
        raise RuntimeError(
            f"Cannot start OAuth callback server on port {CALLBACK_PORT}: {exc}"
        ) from exc

    t = threading.Thread(target=_callback_server.serve_forever, daemon=True)
    t.start()

    # Auto-shutdown after 5 minutes if no callback arrives
    _callback_timer = threading.Timer(300, _shutdown_callback_server)
    _callback_timer.daemon = True
    _callback_timer.start()


def _exchange_tokens(code: str, verifier: str) -> str | None:
    """Exchange authorization code for API key and persist it. Returns error string or None on success."""
    _headers = {"originator": "codex_cli_rs"}
    try:
        with httpx.Client(timeout=30, headers=_headers) as client:
            resp = client.post(TOKEN_URL, data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": verifier,
            })
            if resp.status_code != 200:
                msg = f"Step 1 failed ({resp.status_code}): {resp.text[:300]}"
                logger.error("OpenAI token exchange: %s", msg)
                return msg
            tokens = resp.json()
            id_token = tokens.get("id_token")
            refresh_token = tokens.get("refresh_token", "")
            if not id_token:
                msg = f"Step 1: no id_token in response. Keys: {list(tokens.keys())}"
                logger.error("OpenAI token exchange: %s", msg)
                return msg

            # Try step 2: exchange id_token for an openai-api-key.
            # This requires an org and fails for ChatGPT-only subscribers,
            # so fall back to using the access_token from step 1 directly.
            access_token = tokens.get("access_token", "")
            resp2 = client.post(TOKEN_URL, data={
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "client_id": CLIENT_ID,
                "requested_token": "openai-api-key",
                "subject_token": id_token,
                "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
            })
            if resp2.status_code == 200:
                api_key = resp2.json().get("access_token") or access_token
            else:
                logger.info("OpenAI API key exchange unavailable (%s), using access_token directly", resp2.status_code)
                api_key = access_token
            if not api_key:
                msg = "No access_token in step 1 response and step 2 also failed"
                logger.error("OpenAI token exchange: %s", msg)
                return msg

        from backend.db import set_agent_config
        set_agent_config("openai_access_token", api_key)
        if refresh_token:
            set_agent_config("openai_refresh_token", refresh_token)
        logger.info("OpenAI API key stored successfully")
        return None

    except Exception as exc:
        logger.exception("OpenAI token exchange error")
        return str(exc)
