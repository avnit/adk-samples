"""ADK tool functions backed by the auth providers.

These are plain Python functions -- they can be wrapped as ADK ``FunctionTool``s
(see ``agent.py``) or called directly from tests. The important thing to notice
is that **the tool body is identical regardless of the OAuth flow**: it asks a
provider for auth headers and makes a request. Whether those headers came from a
2-legged (machine) or 3-legged (user) token is entirely the provider's concern.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

from .auth_provider import (
    AuthError,
    OAuthEndpoints,
    ThreeLeggedAuthProvider,
    TwoLeggedAuthProvider,
)

# --------------------------------------------------------------------------
# Provider wiring. In production these come from environment / secret manager.
# For a Wiz-style 2-legged integration you would set, e.g.:
#   OAUTH_TOKEN_URL=https://auth.app.wiz.io/oauth/token
#   OAUTH_CLIENT_ID=...      OAUTH_CLIENT_SECRET=...
# --------------------------------------------------------------------------

_TWO_LEGGED: Optional[TwoLeggedAuthProvider] = None
_THREE_LEGGED: Optional[ThreeLeggedAuthProvider] = None


def configure_providers(
    two_legged: Optional[TwoLeggedAuthProvider] = None,
    three_legged: Optional[ThreeLeggedAuthProvider] = None,
) -> None:
    """Inject providers (used by the demo/tests to point at the mock server)."""
    global _TWO_LEGGED, _THREE_LEGGED
    if two_legged is not None:
        _TWO_LEGGED = two_legged
    if three_legged is not None:
        _THREE_LEGGED = three_legged


def _two_legged() -> TwoLeggedAuthProvider:
    global _TWO_LEGGED
    if _TWO_LEGGED is None:
        _TWO_LEGGED = TwoLeggedAuthProvider(
            endpoints=OAuthEndpoints(token_url=os.environ["OAUTH_TOKEN_URL"]),
            client_id=os.environ["OAUTH_CLIENT_ID"],
            client_secret=os.environ["OAUTH_CLIENT_SECRET"],
            audience=os.environ.get("OAUTH_AUDIENCE"),
            scope=os.environ.get("OAUTH_SCOPE"),
        )
    return _TWO_LEGGED


def _three_legged() -> ThreeLeggedAuthProvider:
    global _THREE_LEGGED
    if _THREE_LEGGED is None:
        _THREE_LEGGED = ThreeLeggedAuthProvider(
            endpoints=OAuthEndpoints(
                token_url=os.environ["OAUTH_TOKEN_URL"],
                authorization_url=os.environ["OAUTH_AUTHORIZATION_URL"],
            ),
            client_id=os.environ["OAUTH_CLIENT_ID"],
            client_secret=os.environ.get("OAUTH_CLIENT_SECRET"),
            redirect_uri=os.environ["OAUTH_REDIRECT_URI"],
            scope=os.environ.get("OAUTH_SCOPE"),
        )
    return _THREE_LEGGED


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------


def list_org_security_findings() -> Dict[str, object]:
    """Return organization-wide security findings.

    Uses **2-legged** auth: the agent authenticates as a service principal, not
    as any particular user, because the findings belong to the whole org. This
    is the right flow for backend/system data (the Wiz integration in this repo
    works exactly this way).

    Returns:
        A dict describing the authenticated call. ``authenticated`` is True when
        a machine token was obtained; ``error`` explains any failure.
    """
    try:
        headers = _two_legged().auth_headers()
    except (AuthError, KeyError) as exc:
        return {"authenticated": False, "error": str(exc)}
    # In a real tool you would now call the API, e.g.:
    #   requests.post(api_url, headers=headers, json=graphql_query)
    return {
        "authenticated": True,
        "flow": "2-legged (client_credentials)",
        "authorization_header_preview": headers["Authorization"][:24] + "...",
        "findings": "<call your security API here with these headers>",
    }


def get_user_profile(user_id: str) -> Dict[str, object]:
    """Return the *calling user's* profile from a user-scoped API.

    Uses **3-legged** auth: the data belongs to a specific person, so the agent
    must act on that user's behalf with a token they consented to. If the user
    has not authorized yet, the tool returns the consent URL they must open.

    Args:
        user_id: Stable identifier for the end user in your system.

    Returns:
        A dict with either the (would-be) profile call, or an
        ``authorization_url`` the user must visit to grant consent.
    """
    provider = _three_legged()
    if not provider.has_credentials(user_id):
        return {
            "authenticated": False,
            "flow": "3-legged (authorization_code)",
            "action_required": "user_consent",
            "authorization_url": provider.create_authorization_url(user_id),
            "message": (
                "Open the authorization_url, approve access, then complete the "
                "OAuth callback so the agent can act on your behalf."
            ),
        }
    try:
        headers = provider.auth_headers(user_id=user_id)
    except AuthError as exc:
        return {"authenticated": False, "error": str(exc)}
    return {
        "authenticated": True,
        "flow": "3-legged (authorization_code)",
        "user_id": user_id,
        "authorization_header_preview": headers["Authorization"][:24] + "...",
        "profile": "<call your user-scoped API here with these headers>",
    }
