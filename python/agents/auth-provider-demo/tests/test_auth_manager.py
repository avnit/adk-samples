"""Tests for the AuthManager named-authorization registry."""

from __future__ import annotations

import unittest
import urllib.error
import urllib.request

from auth_provider_demo import AuthError, AuthManager
from auth_provider_demo.mock_oauth_server import (
    DEMO_CLIENT_ID,
    DEMO_CLIENT_SECRET,
    MockOAuthServer,
)


def _follow_consent(authorization_url: str) -> str:
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    try:
        opener.open(authorization_url)
        raise AssertionError("expected a 302 redirect")
    except urllib.error.HTTPError as exc:
        return exc.headers["Location"]


class AuthManagerTest(unittest.TestCase):
    def setUp(self):
        self.server = MockOAuthServer().start()
        self.addCleanup(self.server.stop)
        self.manager = AuthManager()
        self.manager.register_two_legged(
            "partner-agent",
            token_url=self.server.token_url,
            client_id=DEMO_CLIENT_ID,
            client_secret=DEMO_CLIENT_SECRET,
            description="Service identity for calling a partner agent",
        )
        self.manager.register_three_legged(
            "user-gmail",
            token_url=self.server.token_url,
            authorization_url=self.server.authorize_url,
            client_id=DEMO_CLIENT_ID,
            client_secret=DEMO_CLIENT_SECRET,
            redirect_uri="https://app.example.com/callback",
            scope="read:mail",
            description="Per-user Gmail access",
        )

    def test_duplicate_registration_rejected(self):
        with self.assertRaises(ValueError):
            self.manager.register_two_legged(
                "partner-agent",
                token_url=self.server.token_url,
                client_id=DEMO_CLIENT_ID,
                client_secret=DEMO_CLIENT_SECRET,
            )

    def test_unknown_authorization(self):
        with self.assertRaises(AuthError):
            self.manager.access_token("does-not-exist")

    def test_list_authorizations(self):
        listing = {a["name"]: a for a in self.manager.list_authorizations()}
        self.assertFalse(listing["partner-agent"]["requires_user"])
        self.assertTrue(listing["user-gmail"]["requires_user"])

    def test_two_legged_headers(self):
        headers = self.manager.authorization_headers("partner-agent")
        self.assertTrue(headers["Authorization"].startswith("Bearer app-access-"))

    def test_two_legged_ignores_user(self):
        # Passing a user_id to a 2-legged authorization is harmless.
        token = self.manager.access_token("partner-agent", user_id="whoever")
        self.assertTrue(token.startswith("app-access-"))

    def test_three_legged_requires_user_id(self):
        with self.assertRaises(AuthError):
            self.manager.access_token("user-gmail")

    def test_three_legged_needs_consent_then_resolves(self):
        self.assertTrue(self.manager.needs_consent("user-gmail", user_id="alice"))
        url = self.manager.consent_url("user-gmail", user_id="alice")
        self.manager.complete_consent("user-gmail", _follow_consent(url))
        self.assertFalse(self.manager.needs_consent("user-gmail", user_id="alice"))
        headers = self.manager.authorization_headers("user-gmail", user_id="alice")
        self.assertTrue(headers["Authorization"].startswith("Bearer user-access-"))

    def test_consent_url_rejected_for_two_legged(self):
        with self.assertRaises(AuthError):
            self.manager.consent_url("partner-agent", user_id="alice")

    def test_needs_consent_false_for_two_legged(self):
        self.assertFalse(self.manager.needs_consent("partner-agent", user_id="alice"))


if __name__ == "__main__":
    unittest.main()
