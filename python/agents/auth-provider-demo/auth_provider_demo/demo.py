"""End-to-end, runnable demonstration of the value of an auth provider.

Run it directly -- it spins up the bundled mock OAuth2 server, exercises both
the 2-legged and 3-legged flows through the *same* ``AuthProvider`` interface,
and prints what happens at each step:

    python -m auth_provider_demo.demo

No real credentials, network, or ADK install required.
"""

from __future__ import annotations

import urllib.error
import urllib.request

from .auth_provider import (
    OAuthEndpoints,
    ThreeLeggedAuthProvider,
    TwoLeggedAuthProvider,
)
from .mock_oauth_server import DEMO_CLIENT_ID, DEMO_CLIENT_SECRET, MockOAuthServer


def _simulate_user_consent(authorization_url: str) -> str:
    """Pretend to be the user's browser visiting the consent page.

    A real user would open ``authorization_url``, log in, and click "Allow".
    Our mock server auto-approves and 302-redirects back to the app's
    ``redirect_uri`` with ``?code=...&state=...``. We grab that redirect target
    (the ``Location`` header) without following it -- exactly what a callback
    handler in a web app would receive.
    """

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):  # noqa: D401, ANN002, ANN003
            return None  # do not follow the redirect; we want the Location

    opener = urllib.request.build_opener(_NoRedirect)
    try:
        opener.open(authorization_url)
        raise AssertionError("expected a redirect")
    except urllib.error.HTTPError as exc:  # 302 surfaces here because we blocked it
        return exc.headers["Location"]


def demo_two_legged(token_url: str) -> None:
    print("=" * 72)
    print("2-LEGGED (client_credentials): the agent authenticates AS ITSELF")
    print("=" * 72)

    provider = TwoLeggedAuthProvider(
        endpoints=OAuthEndpoints(token_url=token_url),
        client_id=DEMO_CLIENT_ID,
        client_secret=DEMO_CLIENT_SECRET,
        scope="read:findings",
    )

    # A tool just asks for headers -- it never sees the grant type.
    headers = provider.auth_headers()
    print(f"  grant_type      : {provider.grant_type}")
    print(f"  Authorization   : {headers['Authorization']}")

    # Second call returns the *cached* token (no second network round-trip).
    cached = provider.auth_headers()
    print(f"  cached (reused) : {cached['Authorization'] == headers['Authorization']}")
    print("  -> No user, no browser. Perfect for machine-to-machine APIs (e.g. Wiz).\n")


def demo_three_legged(token_url: str, authorize_url: str) -> None:
    print("=" * 72)
    print("3-LEGGED (authorization_code + PKCE): the agent acts ON BEHALF OF a user")
    print("=" * 72)

    provider = ThreeLeggedAuthProvider(
        endpoints=OAuthEndpoints(token_url=token_url, authorization_url=authorize_url),
        client_id=DEMO_CLIENT_ID,
        client_secret=DEMO_CLIENT_SECRET,
        redirect_uri="https://app.example.com/oauth/callback",
        scope="read:profile",
    )

    user_id = "alice"
    print(f"  user has credentials? {provider.has_credentials(user_id)}  (not yet)")

    # Step 1: build the consent URL the user must approve.
    auth_url = provider.create_authorization_url(user_id)
    print(f"  1. send user to  : {auth_url[:80]}...")

    # Step 2 + 3: user approves; the server redirects back with a code, which we
    # exchange for a per-user token.
    redirect_url = _simulate_user_consent(auth_url)
    print(f"  2. redirected to : {redirect_url[:80]}...")
    provider.fetch_token_from_redirect(redirect_url)
    print(f"  3. exchanged code -> token stored for {user_id!r}")

    # Step 4: tools now use the SAME interface as the 2-legged provider.
    headers = provider.auth_headers(user_id=user_id)
    print(f"  grant_type      : {provider.grant_type}")
    print(f"  Authorization   : {headers['Authorization']}")
    print(f"  user has credentials? {provider.has_credentials(user_id)}  (now yes)")
    print("  -> Consent + PKCE + per-user tokens, all behind the same tiny API.\n")


def main() -> None:
    with MockOAuthServer() as server:
        demo_two_legged(server.token_url)
        demo_three_legged(server.token_url, server.authorize_url)
        print("Both flows satisfied the identical AuthProvider contract:")
        print("  token = provider.get_access_token(...)  /  provider.auth_headers(...)")
        print("That uniformity is the value of the auth provider abstraction.")


if __name__ == "__main__":
    main()
