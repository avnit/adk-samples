"""A central auth manager for agents, tools, A2A peers, and MCP servers.

The :class:`AuthProvider` classes in ``auth_provider.py`` each know how to run a
*single* OAuth2 flow. In a real deployment an agent usually needs *several*
credentials at once: a service identity to call a partner agent (2-legged), a
per-user token to read that user's mailbox through an MCP server (3-legged), a
token to reach a private gateway, and so on.

:class:`AuthManager` is the piece that ties those together. You register each
credential once under a stable **name** ("an authorization"), and every
consumer -- an ADK tool, an A2A client, an MCP connection, a gateway call --
resolves credentials *by name* without knowing or caring which OAuth flow backs
it.

This mirrors how **Gemini Enterprise / Vertex AI Agent Engine** models auth:
you create named *Authorization* resources (client id/secret, auth + token URIs,
scopes) and an agent references them by name; the platform runs the flow and
injects the token. :class:`AuthManager` is a local, runnable stand-in for that
control plane so the notebooks can demonstrate the mechanics end-to-end.

    manager = AuthManager()
    manager.register_two_legged(
        "partner-agent",
        token_url=..., client_id=..., client_secret=...,
    )
    manager.register_three_legged(
        "user-gmail",
        token_url=..., authorization_url=..., client_id=..., redirect_uri=...,
    )

    # 2-legged: no user, one shared token.
    headers = manager.authorization_headers("partner-agent")

    # 3-legged: per user; may require consent first.
    if manager.needs_consent("user-gmail", user_id="alice"):
        url = manager.consent_url("user-gmail", user_id="alice")
        # ... user visits url, approves, you receive the redirect ...
        manager.complete_consent("user-gmail", redirect_url)
    headers = manager.authorization_headers("user-gmail", user_id="alice")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .auth_provider import (
    AuthError,
    AuthProvider,
    OAuthEndpoints,
    ThreeLeggedAuthProvider,
    TokenStore,
    TwoLeggedAuthProvider,
)


@dataclass
class Authorization:
    """A named credential registered with the manager.

    Attributes mirror the fields of a Gemini Enterprise *Authorization*:
    a stable name, the OAuth flow, and the provider that executes it.
    """

    name: str
    flow: str  # "2-legged" | "3-legged"
    provider: AuthProvider
    scopes: Optional[str] = None
    description: str = ""

    @property
    def requires_user(self) -> bool:
        """3-legged authorizations are scoped to an end user; 2-legged are not."""
        return self.flow == "3-legged"


class AuthManager:
    """Registry that resolves named authorizations to access tokens/headers."""

    def __init__(self) -> None:
        self._authorizations: Dict[str, Authorization] = {}

    # -- registration -----------------------------------------------------
    def register(self, authorization: Authorization) -> Authorization:
        if authorization.name in self._authorizations:
            raise ValueError(f"Authorization {authorization.name!r} already registered")
        self._authorizations[authorization.name] = authorization
        return authorization

    def register_two_legged(
        self,
        name: str,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        audience: Optional[str] = None,
        scope: Optional[str] = None,
        description: str = "",
    ) -> Authorization:
        """Register a machine-to-machine (client_credentials) authorization."""
        provider = TwoLeggedAuthProvider(
            endpoints=OAuthEndpoints(token_url=token_url),
            client_id=client_id,
            client_secret=client_secret,
            audience=audience,
            scope=scope,
        )
        return self.register(
            Authorization(
                name=name,
                flow="2-legged",
                provider=provider,
                scopes=scope,
                description=description,
            )
        )

    def register_three_legged(
        self,
        name: str,
        *,
        token_url: str,
        authorization_url: str,
        client_id: str,
        redirect_uri: str,
        client_secret: Optional[str] = None,
        scope: Optional[str] = None,
        token_store: Optional[TokenStore] = None,
        description: str = "",
    ) -> Authorization:
        """Register an on-behalf-of-user (authorization_code + PKCE) authorization."""
        provider = ThreeLeggedAuthProvider(
            endpoints=OAuthEndpoints(
                token_url=token_url, authorization_url=authorization_url
            ),
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            token_store=token_store,
        )
        return self.register(
            Authorization(
                name=name,
                flow="3-legged",
                provider=provider,
                scopes=scope,
                description=description,
            )
        )

    # -- lookup -----------------------------------------------------------
    def get(self, name: str) -> Authorization:
        try:
            return self._authorizations[name]
        except KeyError:
            raise AuthError(
                f"No authorization named {name!r}. Registered: "
                f"{sorted(self._authorizations)}"
            )

    def list_authorizations(self) -> List[Dict[str, object]]:
        """Return a serializable summary of every registered authorization."""
        return [
            {
                "name": a.name,
                "flow": a.flow,
                "requires_user": a.requires_user,
                "scopes": a.scopes,
                "description": a.description,
            }
            for a in self._authorizations.values()
        ]

    # -- 3-legged consent helpers ----------------------------------------
    def needs_consent(self, name: str, *, user_id: str) -> bool:
        """True if a 3-legged authorization has no stored token for the user yet."""
        auth = self.get(name)
        if not auth.requires_user:
            return False
        provider = auth.provider
        assert isinstance(provider, ThreeLeggedAuthProvider)
        return not provider.has_credentials(user_id)

    def consent_url(self, name: str, *, user_id: str) -> str:
        """Return the consent URL a user must visit for a 3-legged authorization."""
        auth = self.get(name)
        if not auth.requires_user:
            raise AuthError(f"Authorization {name!r} is 2-legged; no user consent needed")
        provider = auth.provider
        assert isinstance(provider, ThreeLeggedAuthProvider)
        return provider.create_authorization_url(user_id)

    def complete_consent(self, name: str, redirect_url: str):
        """Finish a 3-legged flow by exchanging the code on the redirect URL."""
        auth = self.get(name)
        if not auth.requires_user:
            raise AuthError(f"Authorization {name!r} is 2-legged; nothing to complete")
        provider = auth.provider
        assert isinstance(provider, ThreeLeggedAuthProvider)
        return provider.fetch_token_from_redirect(redirect_url)

    # -- credential resolution -------------------------------------------
    def access_token(self, name: str, *, user_id: Optional[str] = None) -> str:
        """Return a valid access token for the named authorization."""
        auth = self.get(name)
        if auth.requires_user:
            if not user_id:
                raise AuthError(
                    f"Authorization {name!r} is 3-legged and requires a user_id"
                )
            return auth.provider.get_access_token(user_id=user_id)
        return auth.provider.get_access_token()

    def authorization_headers(
        self, name: str, *, user_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Return ready-to-use ``Authorization`` headers for the named credential."""
        return {"Authorization": f"Bearer {self.access_token(name, user_id=user_id)}"}
