"""Reusable OAuth2 auth providers for ADK agents and tools.

This module demonstrates the *value of an auth provider*: a single, uniform
abstraction that hides the differences between OAuth2 flows from the code that
actually needs an access token.

Two flows are implemented:

* **2-legged OAuth (``TwoLeggedAuthProvider``)** — the OAuth2
  ``client_credentials`` grant. Machine-to-machine: the agent authenticates *as
  itself* using a client id / secret. No human is involved. This is what the
  existing Wiz integration in this repo uses.

* **3-legged OAuth (``ThreeLeggedAuthProvider``)** — the OAuth2
  ``authorization_code`` grant (with PKCE). A human is redirected to an
  authorization server, grants consent, and the resulting code is exchanged for
  a per-user access token + refresh token. This is what you need when the agent
  must act *on behalf of a specific user* (read their calendar, their email,
  their repos, ...).

Both providers expose the same tiny surface:

    token = provider.get_access_token(...)      # -> str
    headers = provider.auth_headers(...)        # -> {"Authorization": "Bearer ..."}

so a tool never has to know *which* flow produced the token. Providers also
transparently cache tokens and refresh them when they expire, which is the
practical payoff of centralizing auth in one place.

The HTTP layer uses only the Python standard library (``urllib``) so the
providers run anywhere without extra dependencies and are easy to unit test
against the bundled mock authorization server.
"""

from __future__ import annotations

import abc
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

# A small safety margin: treat a token as expired this many seconds early so an
# in-flight request never races the real expiry.
_EXPIRY_SKEW_SECONDS = 60


class AuthError(RuntimeError):
    """Raised when authentication or token exchange fails."""


@dataclass
class Token:
    """An OAuth2 token with just enough metadata to know when to refresh it."""

    access_token: str
    token_type: str = "Bearer"
    expires_at: Optional[float] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None

    @classmethod
    def from_response(cls, data: Dict, *, now: Optional[float] = None) -> "Token":
        """Build a :class:`Token` from a standard OAuth2 token endpoint payload."""
        now = time.time() if now is None else now
        expires_in = data.get("expires_in")
        expires_at = now + float(expires_in) if expires_in is not None else None
        return cls(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=expires_at,
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
        )

    def is_expired(self, *, now: Optional[float] = None, skew: float = _EXPIRY_SKEW_SECONDS) -> bool:
        """Return ``True`` if the token is missing an expiry-safe window."""
        if self.expires_at is None:
            return False
        now = time.time() if now is None else now
        return now >= (self.expires_at - skew)

    @property
    def authorization_header(self) -> str:
        return f"{self.token_type} {self.access_token}"


@dataclass
class OAuthEndpoints:
    """Where to talk to the authorization server."""

    token_url: str
    # Only required for 3-legged (authorization_code) flows.
    authorization_url: Optional[str] = None


def _post_form(url: str, form: Dict[str, str], *, timeout: float = 30.0) -> Dict:
    """POST an ``application/x-www-form-urlencoded`` body and parse JSON back.

    Uses ``urllib`` so the providers have no third-party dependency.
    """
    body = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (trusted URL)
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:  # pragma: no cover - network error path
        detail = exc.read().decode("utf-8", "replace")
        raise AuthError(f"Token endpoint returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network error path
        raise AuthError(f"Could not reach token endpoint {url}: {exc.reason}") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AuthError(f"Token endpoint returned non-JSON body: {payload!r}") from exc

    if "error" in data:
        raise AuthError(
            f"Token endpoint returned error {data.get('error')!r}: "
            f"{data.get('error_description', 'no description')}"
        )
    if "access_token" not in data:
        raise AuthError(f"Token endpoint response missing access_token: {data!r}")
    return data


class AuthProvider(abc.ABC):
    """Common interface shared by every OAuth flow.

    Tools depend only on this abstraction, never on a specific grant type. That
    is the whole point: swap a 2-legged provider for a 3-legged one and the tool
    code does not change.
    """

    #: Human readable name of the flow, handy for logs / demos.
    grant_type: str = "abstract"

    @abc.abstractmethod
    def get_access_token(self, **kwargs) -> str:
        """Return a valid access token, fetching or refreshing as needed."""

    def auth_headers(self, **kwargs) -> Dict[str, str]:
        """Return ready-to-use ``Authorization`` headers for an API call."""
        return {"Authorization": f"Bearer {self.get_access_token(**kwargs)}"}


class TwoLeggedAuthProvider(AuthProvider):
    """OAuth2 ``client_credentials`` (2-legged / machine-to-machine) provider.

    The agent authenticates *as itself*. There is exactly one token shared by
    the whole process, cached until it is about to expire and then silently
    re-fetched. No user, no browser, no refresh token.
    """

    grant_type = "client_credentials"

    def __init__(
        self,
        *,
        endpoints: OAuthEndpoints,
        client_id: str,
        client_secret: str,
        audience: Optional[str] = None,
        scope: Optional[str] = None,
        transport: Callable[[str, Dict[str, str]], Dict] = _post_form,
    ) -> None:
        self._endpoints = endpoints
        self._client_id = client_id
        self._client_secret = client_secret
        self._audience = audience
        self._scope = scope
        self._transport = transport
        self._token: Optional[Token] = None
        self._lock = threading.Lock()

    def _fetch_token(self) -> Token:
        form = {
            "grant_type": self.grant_type,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if self._audience:
            form["audience"] = self._audience
        if self._scope:
            form["scope"] = self._scope
        return Token.from_response(self._transport(self._endpoints.token_url, form))

    def get_access_token(self, *, force_refresh: bool = False, **_: object) -> str:
        with self._lock:
            if force_refresh or self._token is None or self._token.is_expired():
                self._token = self._fetch_token()
            return self._token.access_token

    @classmethod
    def from_env(
        cls,
        *,
        token_url_env: str,
        client_id_env: str,
        client_secret_env: str,
        audience: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> "TwoLeggedAuthProvider":
        """Build a provider from environment variables (keeps secrets out of code)."""
        token_url = os.environ.get(token_url_env)
        client_id = os.environ.get(client_id_env)
        client_secret = os.environ.get(client_secret_env)
        missing = [
            name
            for name, value in (
                (token_url_env, token_url),
                (client_id_env, client_id),
                (client_secret_env, client_secret),
            )
            if not value
        ]
        if missing:
            raise AuthError(f"Missing required environment variables: {', '.join(missing)}")
        return cls(
            endpoints=OAuthEndpoints(token_url=token_url),
            client_id=client_id,
            client_secret=client_secret,
            audience=audience,
            scope=scope,
        )


class TokenStore(abc.ABC):
    """Per-user token persistence used by the 3-legged flow.

    In production this would be backed by a database / secret manager so a
    returning user does not have to re-consent. The in-memory implementation
    below is enough for demos and tests.
    """

    @abc.abstractmethod
    def get(self, user_id: str) -> Optional[Token]:
        ...

    @abc.abstractmethod
    def set(self, user_id: str, token: Token) -> None:
        ...

    @abc.abstractmethod
    def delete(self, user_id: str) -> None:
        ...


class InMemoryTokenStore(TokenStore):
    """Thread-safe dictionary-backed token store."""

    def __init__(self) -> None:
        self._tokens: Dict[str, Token] = {}
        self._lock = threading.Lock()

    def get(self, user_id: str) -> Optional[Token]:
        with self._lock:
            return self._tokens.get(user_id)

    def set(self, user_id: str, token: Token) -> None:
        with self._lock:
            self._tokens[user_id] = token

    def delete(self, user_id: str) -> None:
        with self._lock:
            self._tokens.pop(user_id, None)


@dataclass
class PendingAuthorization:
    """State carried between "build authorization URL" and "handle redirect"."""

    user_id: str
    state: str
    code_verifier: str
    redirect_uri: str
    scope: Optional[str] = None


class ThreeLeggedAuthProvider(AuthProvider):
    """OAuth2 ``authorization_code`` (3-legged / on-behalf-of-user) provider.

    Flow:

    1. :meth:`create_authorization_url` — build the consent URL (with PKCE +
       CSRF ``state``) the user must visit and store the pending state.
    2. The user approves; the authorization server redirects back with a
       ``code`` and the ``state`` echoed.
    3. :meth:`fetch_token_from_redirect` — validate ``state``, exchange the
       ``code`` (+ PKCE verifier) for a token, and persist it per-user.
    4. :meth:`get_access_token` — hand back the cached token, using the stored
       ``refresh_token`` to renew it transparently once it expires.

    Because it implements the same :class:`AuthProvider` interface, a tool can
    consume a per-user token exactly like it consumes a machine token.
    """

    grant_type = "authorization_code"

    def __init__(
        self,
        *,
        endpoints: OAuthEndpoints,
        client_id: str,
        client_secret: Optional[str] = None,
        redirect_uri: str,
        scope: Optional[str] = None,
        token_store: Optional[TokenStore] = None,
        transport: Callable[[str, Dict[str, str]], Dict] = _post_form,
    ) -> None:
        if not endpoints.authorization_url:
            raise AuthError("3-legged flow requires endpoints.authorization_url")
        self._endpoints = endpoints
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._scope = scope
        self._store = token_store or InMemoryTokenStore()
        self._transport = transport
        self._pending: Dict[str, PendingAuthorization] = {}
        self._lock = threading.Lock()

    # -- step 1: build the consent URL ------------------------------------
    @staticmethod
    def _pkce_pair() -> tuple[str, str]:
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        return verifier, challenge

    def create_authorization_url(self, user_id: str) -> str:
        """Return the URL the user must open to grant consent."""
        verifier, challenge = self._pkce_pair()
        state = secrets.token_urlsafe(24)
        pending = PendingAuthorization(
            user_id=user_id,
            state=state,
            code_verifier=verifier,
            redirect_uri=self._redirect_uri,
            scope=self._scope,
        )
        with self._lock:
            self._pending[state] = pending

        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if self._scope:
            params["scope"] = self._scope
        return f"{self._endpoints.authorization_url}?{urllib.parse.urlencode(params)}"

    # -- step 3: exchange the returned code -------------------------------
    def fetch_token_from_redirect(self, redirect_url: str) -> Token:
        """Handle the redirect back from the authorization server.

        ``redirect_url`` is the full URL the browser was sent to, e.g.
        ``https://app/callback?code=...&state=...``.
        """
        query = urllib.parse.urlparse(redirect_url).query
        params = dict(urllib.parse.parse_qsl(query))
        if "error" in params:
            raise AuthError(
                f"Authorization server returned error {params['error']!r}: "
                f"{params.get('error_description', 'no description')}"
            )
        state = params.get("state")
        code = params.get("code")
        if not state or not code:
            raise AuthError("Redirect is missing 'code' or 'state'")

        with self._lock:
            pending = self._pending.pop(state, None)
        if pending is None:
            # Unknown/expired state -> possible CSRF. Refuse the exchange.
            raise AuthError("Unknown or reused 'state' value; possible CSRF attempt")

        form = {
            "grant_type": self.grant_type,
            "code": code,
            "redirect_uri": pending.redirect_uri,
            "client_id": self._client_id,
            "code_verifier": pending.code_verifier,
        }
        if self._client_secret:
            form["client_secret"] = self._client_secret
        token = Token.from_response(self._transport(self._endpoints.token_url, form))
        self._store.set(pending.user_id, token)
        return token

    # -- step 4: use / refresh the token ----------------------------------
    def _refresh(self, refresh_token: str) -> Token:
        form = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._client_id,
        }
        if self._client_secret:
            form["client_secret"] = self._client_secret
        data = self._transport(self._endpoints.token_url, form)
        new_token = Token.from_response(data)
        # Some servers omit the refresh_token on refresh; keep the old one.
        if new_token.refresh_token is None:
            new_token.refresh_token = refresh_token
        return new_token

    def has_credentials(self, user_id: str) -> bool:
        """Return ``True`` if the user has already consented (token on file)."""
        return self._store.get(user_id) is not None

    def get_access_token(self, *, user_id: str, **_: object) -> str:  # type: ignore[override]
        with self._lock:
            token = self._store.get(user_id)
            if token is None:
                raise AuthError(
                    f"No token for user {user_id!r}. Call create_authorization_url() "
                    "and complete the consent flow first."
                )
            if token.is_expired():
                if not token.refresh_token:
                    raise AuthError(
                        f"Token for user {user_id!r} expired and no refresh_token is "
                        "available; the user must re-authorize."
                    )
                token = self._refresh(token.refresh_token)
                self._store.set(user_id, token)
            return token.access_token
