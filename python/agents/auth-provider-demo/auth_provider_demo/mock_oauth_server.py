"""A tiny, dependency-free mock OAuth2 authorization server.

It implements just enough of the spec to exercise both the 2-legged
(``client_credentials``) and 3-legged (``authorization_code`` + PKCE +
``refresh_token``) flows end-to-end, so the demo and the tests run without any
real identity provider or network access.

    server = MockOAuthServer(users={"alice": "s3cret"})
    server.start()
    print(server.token_url, server.authorize_url)
    ...
    server.stop()

This is a test/demo fixture only — do not use it as a real authorization server.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional

# Static client the demo authenticates as.
DEMO_CLIENT_ID = "demo-client-id"
DEMO_CLIENT_SECRET = "demo-client-secret"

# Tokens expire quickly so the demo can show refresh without waiting.
ACCESS_TOKEN_TTL_SECONDS = 3600


@dataclass
class _AuthCode:
    user_id: str
    code_challenge: str
    redirect_uri: str
    scope: Optional[str]


@dataclass
class _IssuedToken:
    user_id: str
    scope: Optional[str]
    kind: str  # "app" (2-legged) or "user" (3-legged)


class _State:
    """Shared mutable state across handler threads."""

    def __init__(self, users: Dict[str, str]) -> None:
        self.users = users
        self.auth_codes: Dict[str, _AuthCode] = {}
        self.refresh_tokens: Dict[str, _IssuedToken] = {}
        self.counter = 0
        self.lock = threading.Lock()

    def next_id(self) -> int:
        with self.lock:
            self.counter += 1
            return self.counter


def _b64_challenge(verifier: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )


def _make_handler(state: _State):
    class Handler(BaseHTTPRequestHandler):
        # Silence the default request logging so demo/test output stays clean.
        def log_message(self, *args, **kwargs):  # noqa: D401, ANN002, ANN003
            return

        def _json(self, code: int, payload: Dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # --- 3-legged step 1: the consent / authorization endpoint --------
        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/authorize":
                self._json(404, {"error": "not_found"})
                return

            params = dict(urllib.parse.parse_qsl(parsed.query))
            redirect_uri = params.get("redirect_uri", "")
            csrf_state = params.get("state", "")

            # A real server would render a login + consent page here. The mock
            # auto-approves for the demo user and immediately issues a code.
            user_id = params.get("login_as", "demo-user")
            code = f"auth-code-{state_next(state_obj)}"
            state_obj.auth_codes[code] = _AuthCode(
                user_id=user_id,
                code_challenge=params.get("code_challenge", ""),
                redirect_uri=redirect_uri,
                scope=params.get("scope"),
            )
            location = f"{redirect_uri}?{urllib.parse.urlencode({'code': code, 'state': csrf_state})}"
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()

        # --- token endpoint: serves every grant type ----------------------
        def do_POST(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/token":
                self._json(404, {"error": "not_found"})
                return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            form = dict(urllib.parse.parse_qsl(body))
            grant_type = form.get("grant_type")

            if grant_type == "client_credentials":
                self._client_credentials(form)
            elif grant_type == "authorization_code":
                self._authorization_code(form)
            elif grant_type == "refresh_token":
                self._refresh_token(form)
            else:
                self._json(400, {"error": "unsupported_grant_type"})

        # 2-legged: authenticate the client itself.
        def _client_credentials(self, form: Dict[str, str]) -> None:
            if (
                form.get("client_id") != DEMO_CLIENT_ID
                or form.get("client_secret") != DEMO_CLIENT_SECRET
            ):
                self._json(401, {"error": "invalid_client"})
                return
            token = f"app-access-{state_next(state_obj)}"
            self._json(
                200,
                {
                    "access_token": token,
                    "token_type": "Bearer",
                    "expires_in": ACCESS_TOKEN_TTL_SECONDS,
                    "scope": form.get("scope", ""),
                },
            )

        # 3-legged step 3: exchange the authorization code (verify PKCE).
        def _authorization_code(self, form: Dict[str, str]) -> None:
            code = form.get("code", "")
            record = state_obj.auth_codes.pop(code, None)
            if record is None:
                self._json(400, {"error": "invalid_grant", "error_description": "bad code"})
                return
            verifier = form.get("code_verifier", "")
            if record.code_challenge and _b64_challenge(verifier) != record.code_challenge:
                self._json(
                    400,
                    {"error": "invalid_grant", "error_description": "PKCE verification failed"},
                )
                return
            if form.get("redirect_uri") != record.redirect_uri:
                self._json(
                    400,
                    {"error": "invalid_grant", "error_description": "redirect_uri mismatch"},
                )
                return

            refresh_token = f"refresh-{record.user_id}-{state_next(state_obj)}"
            state_obj.refresh_tokens[refresh_token] = _IssuedToken(
                user_id=record.user_id, scope=record.scope, kind="user"
            )
            self._json(
                200,
                {
                    "access_token": f"user-access-{record.user_id}-{state_next(state_obj)}",
                    "token_type": "Bearer",
                    "expires_in": ACCESS_TOKEN_TTL_SECONDS,
                    "refresh_token": refresh_token,
                    "scope": record.scope or "",
                },
            )

        # 3-legged step 4: mint a fresh access token from a refresh token.
        def _refresh_token(self, form: Dict[str, str]) -> None:
            refresh_token = form.get("refresh_token", "")
            record = state_obj.refresh_tokens.get(refresh_token)
            if record is None:
                self._json(400, {"error": "invalid_grant", "error_description": "bad refresh"})
                return
            self._json(
                200,
                {
                    "access_token": f"user-access-{record.user_id}-{state_next(state_obj)}",
                    "token_type": "Bearer",
                    "expires_in": ACCESS_TOKEN_TTL_SECONDS,
                    # Deliberately omit refresh_token to exercise the provider's
                    # "reuse the old refresh token" path.
                    "scope": record.scope or "",
                },
            )

    return Handler


# Handlers are created per-connection, so counter state lives on the module-level
# _State instance referenced through these closures set up in MockOAuthServer.
state_obj: Optional[_State] = None


def state_next(state: _State) -> int:
    return state.next_id()


class MockOAuthServer:
    """Threaded mock OAuth2 server usable as a context manager."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._host = host
        self._port = port
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._state = _State(users={"demo-user": "password"})

    def start(self) -> "MockOAuthServer":
        global state_obj
        state_obj = self._state
        handler = _make_handler(self._state)
        self._httpd = ThreadingHTTPServer((self._host, self._port), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    @property
    def base_url(self) -> str:
        assert self._httpd is not None, "server not started"
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"

    @property
    def token_url(self) -> str:
        return f"{self.base_url}/token"

    @property
    def authorize_url(self) -> str:
        return f"{self.base_url}/authorize"

    def __enter__(self) -> "MockOAuthServer":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
