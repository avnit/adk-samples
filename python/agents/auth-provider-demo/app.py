"""Flask API server for the Auth Provider Demo.

Exposes OAuth2 authentication flows (2-legged and 3-legged) as REST endpoints.
Suitable for deployment on Google Cloud Run.
"""

import json
import logging
import os
from flask import Flask, jsonify, request

from auth_provider_demo.auth_manager import AuthManager
from auth_provider_demo.auth_provider import (
    TwoLeggedAuthProvider,
    ThreeLeggedAuthProvider,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize auth manager with demo providers
auth_manager = AuthManager()

# Register 2-legged auth (client_credentials)
two_legged = TwoLeggedAuthProvider(
    client_id=os.getenv("CLIENT_ID", "demo-client-id"),
    client_secret=os.getenv("CLIENT_SECRET", "demo-client-secret"),
    token_url=os.getenv("TOKEN_URL", "http://localhost:8081/token"),
)
auth_manager.register("machine-auth", two_legged)

# Register 3-legged auth (authorization_code)
three_legged = ThreeLeggedAuthProvider(
    client_id=os.getenv("OAUTH_CLIENT_ID", "demo-oauth-client-id"),
    client_secret=os.getenv("OAUTH_CLIENT_SECRET", "demo-oauth-secret"),
    authorization_url=os.getenv(
        "AUTHORIZATION_URL", "http://localhost:8081/authorize"
    ),
    token_url=os.getenv("OAUTH_TOKEN_URL", "http://localhost:8081/token"),
    redirect_uri=os.getenv(
        "REDIRECT_URI",
        "https://app.example.com/oauth/callback",
    ),
)
auth_manager.register("user-auth", three_legged)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "healthy"}), 200


@app.route("/api/v1/health", methods=["GET"])
def api_health():
    """API health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "service": "auth-provider-demo",
            "version": "0.1.0",
        }
    ), 200


@app.route("/api/v1/auth/providers", methods=["GET"])
def list_providers():
    """List registered authentication providers."""
    providers = list(auth_manager.providers.keys())
    return jsonify({"providers": providers}), 200


@app.route("/api/v1/auth/<provider_name>/token", methods=["POST"])
def get_token(provider_name):
    """Get an access token from the specified provider.

    For 2-legged auth:
        POST /api/v1/auth/machine-auth/token
        {}

    For 3-legged auth:
        POST /api/v1/auth/user-auth/token
        {"user_id": "alice"}
    """
    try:
        provider = auth_manager.get_provider(provider_name)
        if not provider:
            return jsonify({"error": f"Provider not found: {provider_name}"}), 404

        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")

        token = provider.get_access_token(user_id=user_id)
        return (
            jsonify(
                {
                    "access_token": token,
                    "token_type": "Bearer",
                    "provider": provider_name,
                    "user_id": user_id,
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Error getting token: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/auth/<provider_name>/headers", methods=["POST"])
def get_auth_headers(provider_name):
    """Get authorization headers from the specified provider.

    Returns a dict like: {"Authorization": "Bearer <token>"}
    """
    try:
        provider = auth_manager.get_provider(provider_name)
        if not provider:
            return jsonify({"error": f"Provider not found: {provider_name}"}), 404

        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")

        headers = provider.auth_headers(user_id=user_id)
        return jsonify({"headers": headers, "provider": provider_name}), 200
    except Exception as e:
        logger.error(f"Error getting auth headers: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/oauth/authorize", methods=["GET"])
def oauth_authorize():
    """3-legged OAuth authorization endpoint.

    Initiates the authorization code flow.
    Query params: state (CSRF token), scope, etc.
    """
    try:
        state = request.args.get("state")
        scope = request.args.get("scope", "default")

        provider = auth_manager.get_provider("user-auth")
        if not provider:
            return jsonify({"error": "User auth provider not configured"}), 500

        # Generate authorization URL
        auth_url = provider.get_authorization_url(state=state)
        return jsonify({"authorization_url": auth_url}), 200
    except Exception as e:
        logger.error(f"Error in authorization: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/oauth/callback", methods=["POST"])
def oauth_callback():
    """3-legged OAuth callback endpoint.

    Exchanges authorization code for access token.
    Body: {"code": "<auth_code>", "state": "<state>", "user_id": "<user>"}
    """
    try:
        data = request.get_json() or {}
        code = data.get("code")
        state = data.get("state")
        user_id = data.get("user_id", "default-user")

        if not code:
            return jsonify({"error": "Missing authorization code"}), 400

        provider = auth_manager.get_provider("user-auth")
        if not provider:
            return jsonify({"error": "User auth provider not configured"}), 500

        # Exchange code for token
        token = provider.exchange_code_for_token(code, state)
        return (
            jsonify(
                {
                    "access_token": token,
                    "token_type": "Bearer",
                    "user_id": user_id,
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Error in callback: {e}")
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors."""
    logger.error(f"Internal error: {e}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
