"""Tests for the 2-legged and 3-legged auth providers.

Uses the bundled mock OAuth2 server so everything runs offline with only the
standard library (``python -m unittest`` or ``pytest`` both work).
"""

from __future__ import annotations

import time
import unittest
import urllib.error
import urllib.request

from auth_provider_demo import tools
from auth_provider_demo.auth_provider import (
    AuthError,
    OAuthEndpoints,
    ThreeLeggedAuthProvider,
    Token,
    TwoLeggedAuthProvider,
)
from auth_provider_demo.mock_oauth_server import (
    DEMO_CLIENT_ID,
    DEMO_CLIENT_SECRET,
    MockOAuthServer,
)


def _follow_consent(authorization_url: str) -> str:
    """Visit the consent URL and return the redirect (with code+state)."""

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    try:
        opener.open(authorization_url)
        raise AssertionError("expected a 302 redirect")
    except urllib.error.HTTPError as exc:
        return exc.headers["Location"]


class TokenTest(unittest.TestCase):
    def test_expiry_with_skew(self):
        now = 1000.0
        token = Token(access_token="x", expires_at=now + 30)
        # 30s left but default skew is 60s -> considered expired.
        self.assertTrue(token.is_expired(now=now))
        self.assertFalse(token.is_expired(now=now, skew=0))

    def test_no_expiry_never_expires(self):
        self.assertFalse(Token(access_token="x").is_expired())


class TwoLeggedTest(unittest.TestCase):
    def setUp(self):
        self.server = MockOAuthServer().start()
        self.addCleanup(self.server.stop)
        self.provider = TwoLeggedAuthProvider(
            endpoints=OAuthEndpoints(token_url=self.server.token_url),
            client_id=DEMO_CLIENT_ID,
            client_secret=DEMO_CLIENT_SECRET,
        )

    def test_fetches_token(self):
        token = self.provider.get_access_token()
        self.assertTrue(token.startswith("app-access-"))

    def test_caches_token(self):
        first = self.provider.get_access_token()
        second = self.provider.get_access_token()
        self.assertEqual(first, second)

    def test_force_refresh_gets_new_token(self):
        first = self.provider.get_access_token()
        second = self.provider.get_access_token(force_refresh=True)
        self.assertNotEqual(first, second)

    def test_auth_headers(self):
        headers = self.provider.auth_headers()
        self.assertTrue(headers["Authorization"].startswith("Bearer app-access-"))

    def test_bad_client_raises(self):
        provider = TwoLeggedAuthProvider(
            endpoints=OAuthEndpoints(token_url=self.server.token_url),
            client_id="wrong",
            client_secret="wrong",
        )
        with self.assertRaises(AuthError):
            provider.get_access_token()


class ThreeLeggedTest(unittest.TestCase):
    def setUp(self):
        self.server = MockOAuthServer().start()
        self.addCleanup(self.server.stop)
        self.provider = ThreeLeggedAuthProvider(
            endpoints=OAuthEndpoints(
                token_url=self.server.token_url,
                authorization_url=self.server.authorize_url,
            ),
            client_id=DEMO_CLIENT_ID,
            client_secret=DEMO_CLIENT_SECRET,
            redirect_uri="https://app.example.com/callback",
            scope="read:profile",
        )

    def _consent(self, user_id="alice"):
        url = self.provider.create_authorization_url(user_id)
        redirect = _follow_consent(url)
        return self.provider.fetch_token_from_redirect(redirect)

    def test_requires_authorization_url(self):
        with self.assertRaises(AuthError):
            ThreeLeggedAuthProvider(
                endpoints=OAuthEndpoints(token_url=self.server.token_url),
                client_id=DEMO_CLIENT_ID,
                redirect_uri="https://app/callback",
            )

    def test_no_credentials_before_consent(self):
        self.assertFalse(self.provider.has_credentials("alice"))
        with self.assertRaises(AuthError):
            self.provider.get_access_token(user_id="alice")

    def test_full_consent_flow(self):
        token = self._consent("alice")
        self.assertTrue(token.access_token.startswith("user-access-"))
        self.assertIsNotNone(token.refresh_token)
        self.assertTrue(self.provider.has_credentials("alice"))
        headers = self.provider.auth_headers(user_id="alice")
        self.assertTrue(headers["Authorization"].startswith("Bearer user-access-"))

    def test_csrf_state_rejected(self):
        self.provider.create_authorization_url("alice")
        bad = "https://app.example.com/callback?code=abc&state=forged-state"
        with self.assertRaises(AuthError):
            self.provider.fetch_token_from_redirect(bad)

    def test_error_redirect(self):
        bad = "https://app.example.com/callback?error=access_denied"
        with self.assertRaises(AuthError):
            self.provider.fetch_token_from_redirect(bad)

    def test_refresh_when_expired(self):
        self._consent("alice")
        # Force the stored token to look expired so get_access_token refreshes.
        stored = self.provider._store.get("alice")
        stored.expires_at = time.time() - 1
        self.provider._store.set("alice", stored)
        refreshed = self.provider.get_access_token(user_id="alice")
        self.assertTrue(refreshed.startswith("user-access-"))
        # Refresh token is preserved even though the server omitted it.
        self.assertIsNotNone(self.provider._store.get("alice").refresh_token)


class ToolsTest(unittest.TestCase):
    """The provider abstraction lets the tools stay flow-agnostic."""

    def setUp(self):
        self.server = MockOAuthServer().start()
        self.addCleanup(self.server.stop)
        tools.configure_providers(
            two_legged=TwoLeggedAuthProvider(
                endpoints=OAuthEndpoints(token_url=self.server.token_url),
                client_id=DEMO_CLIENT_ID,
                client_secret=DEMO_CLIENT_SECRET,
            ),
            three_legged=ThreeLeggedAuthProvider(
                endpoints=OAuthEndpoints(
                    token_url=self.server.token_url,
                    authorization_url=self.server.authorize_url,
                ),
                client_id=DEMO_CLIENT_ID,
                client_secret=DEMO_CLIENT_SECRET,
                redirect_uri="https://app.example.com/callback",
            ),
        )

    def test_two_legged_tool(self):
        result = tools.list_org_security_findings()
        self.assertTrue(result["authenticated"])
        self.assertIn("2-legged", result["flow"])

    def test_three_legged_tool_requires_consent_first(self):
        result = tools.get_user_profile("bob")
        self.assertFalse(result["authenticated"])
        self.assertEqual(result["action_required"], "user_consent")
        self.assertIn("authorization_url", result)

    def test_three_legged_tool_after_consent(self):
        provider = tools._three_legged()
        url = provider.create_authorization_url("bob")
        provider.fetch_token_from_redirect(_follow_consent(url))
        result = tools.get_user_profile("bob")
        self.assertTrue(result["authenticated"])
        self.assertEqual(result["user_id"], "bob")


if __name__ == "__main__":
    unittest.main()
