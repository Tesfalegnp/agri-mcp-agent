"""Automated tests for OAuth 2.1 authorization, PKCE, token verification, and scope protection."""

from __future__ import annotations

import base64
import hashlib
import time
import pytest
from fastapi.testclient import TestClient

from agricultural_assistant.api.app import create_app
from agricultural_assistant.config import Settings
from agricultural_assistant.server.oauth import OAuth2Manager, sanitize_secrets


@pytest.fixture
def oauth_manager() -> OAuth2Manager:
    """Fresh isolated OAuth2Manager instance."""
    return OAuth2Manager(
        issuer="http://testserver",
        jwt_secret="test-oauth-jwt-secret-key-32bytes-min!!",
        token_lifetime_seconds=2,  # Short expiry for test validation
        auth_code_lifetime_seconds=10,
    )


@pytest.fixture
def test_client() -> TestClient:
    """FastAPI TestClient with OAuth protection enabled and active lifespan."""
    app = create_app(settings=Settings(app_env="testing"))
    with TestClient(app) as client:
        yield client


def generate_pkce_pair(verifier: str = "secure_random_verifier_string_at_least_43_chars_long_123456789") -> tuple[str, str]:
    """Compute S256 code challenge for verifier."""
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


class TestOAuth2ServerAndPKCE:
    """Test OAuth 2.1 authorization server flows."""

    def test_authorization_server_metadata(self, test_client: TestClient) -> None:
        """RFC 8414 Authorization Server Metadata endpoint returns valid configuration."""
        resp = test_client.get("/.well-known/oauth-authorization-server")
        assert resp.status_code == 200
        data = resp.json()
        assert "authorization_endpoint" in data
        assert "token_endpoint" in data
        assert "code_challenge_methods_supported" in data
        assert "S256" in data["code_challenge_methods_supported"]
        assert "agri:read" in data["scopes_supported"]
        assert "agri:write" in data["scopes_supported"]

    def test_pkce_authorization_code_flow_success(self, oauth_manager: OAuth2Manager) -> None:
        """Successful authorization code flow with S256 PKCE verification."""
        verifier, challenge = generate_pkce_pair()

        # 1. Authorize: Request code
        code = oauth_manager.create_authorization_code(
            client_id="agri-web-client",
            redirect_uri="http://localhost:5173/oauth/callback",
            scope="agri:read agri:write",
            code_challenge=challenge,
            code_challenge_method="S256",
        )
        assert code.startswith("authcode_")

        # 2. Token Exchange: Exchange code + verifier
        token_resp = oauth_manager.exchange_authorization_code(
            code=code,
            client_id="agri-web-client",
            code_verifier=verifier,
            redirect_uri="http://localhost:5173/oauth/callback",
        )
        assert "access_token" in token_resp
        assert token_resp["token_type"] == "Bearer"
        assert "agri:read" in token_resp["scope"]
        assert "agri:write" in token_resp["scope"]

    def test_pkce_invalid_verifier_rejected(self, oauth_manager: OAuth2Manager) -> None:
        """Reject token exchange when PKCE verifier does not match challenge."""
        _, challenge = generate_pkce_pair("correct_verifier_long_enough_12345678901234567890")

        code = oauth_manager.create_authorization_code(
            client_id="agri-web-client",
            redirect_uri="http://localhost:5173/oauth/callback",
            scope="agri:read",
            code_challenge=challenge,
            code_challenge_method="S256",
        )

        with pytest.raises(ValueError, match="Invalid PKCE code_verifier"):
            oauth_manager.exchange_authorization_code(
                code=code,
                client_id="agri-web-client",
                code_verifier="wrong_verifier_guess_12345678901234567890",
            )

    def test_pkce_invalid_redirect_uri_rejected(self, oauth_manager: OAuth2Manager) -> None:
        """Reject authorization code request when redirect_uri is not registered for client."""
        _, challenge = generate_pkce_pair()
        with pytest.raises(ValueError, match="Invalid redirect_uri"):
            oauth_manager.create_authorization_code(
                client_id="agri-web-client",
                redirect_uri="https://attacker.evil.com/steal-code",
                scope="agri:read",
                code_challenge=challenge,
                code_challenge_method="S256",
            )

    def test_authorization_code_replay_rejected(self, oauth_manager: OAuth2Manager) -> None:
        """Authorization codes must be single-use only."""
        verifier, challenge = generate_pkce_pair()
        code = oauth_manager.create_authorization_code(
            client_id="agri-web-client",
            redirect_uri="http://localhost:5173/oauth/callback",
            scope="agri:read",
            code_challenge=challenge,
        )

        # First use succeeds
        oauth_manager.exchange_authorization_code(
            code=code,
            client_id="agri-web-client",
            code_verifier=verifier,
        )

        # Second use must fail
        with pytest.raises(ValueError, match="Invalid authorization code"):
            oauth_manager.exchange_authorization_code(
                code=code,
                client_id="agri-web-client",
                code_verifier=verifier,
            )

    def test_client_credentials_grant_success(self, oauth_manager: OAuth2Manager) -> None:
        """Confidential client credentials grant succeeds with valid secret."""
        token_resp = oauth_manager.exchange_client_credentials(
            client_id="agri-evaluator-client",
            client_secret="evaluator-secret-key-2026",
            scope="agri:read agri:write",
        )
        assert "access_token" in token_resp
        assert "agri:write" in token_resp["scope"]

    def test_client_credentials_invalid_secret_rejected(self, oauth_manager: OAuth2Manager) -> None:
        """Reject client credentials with incorrect secret."""
        with pytest.raises(ValueError, match="Invalid client credentials"):
            oauth_manager.exchange_client_credentials(
                client_id="agri-evaluator-client",
                client_secret="wrong-secret-xyz",
            )


class TestTokenVerificationAndScopes:
    """Test token verification, expiration, scopes, and revocation."""

    @pytest.mark.anyio
    async def test_valid_token_verification(self, oauth_manager: OAuth2Manager) -> None:
        """Verify that a freshly minted token is successfully validated."""
        res = oauth_manager._issue_token_response(
            client_id="agri-web-client",
            scopes=["agri:read", "agri:write"],
            subject="farmer_123",
        )
        token = res["access_token"]
        token_info = await oauth_manager.verify_token(token)
        assert token_info is not None
        assert token_info.client_id == "agri-web-client"
        assert token_info.subject == "farmer_123"
        assert "agri:read" in token_info.scopes
        assert "agri:write" in token_info.scopes

    @pytest.mark.anyio
    async def test_expired_token_rejected(self, oauth_manager: OAuth2Manager) -> None:
        """Reject token once its expiration time has passed."""
        # Create token with 1 second lifetime
        oauth_manager.token_lifetime_seconds = 1
        res = oauth_manager._issue_token_response(
            client_id="agri-web-client",
            scopes=["agri:read"],
            subject="farmer_123",
        )
        token = res["access_token"]

        # Wait for expiration
        time.sleep(1.2)
        token_info = await oauth_manager.verify_token(token)
        assert token_info is None

    @pytest.mark.anyio
    async def test_tampered_token_rejected(self, oauth_manager: OAuth2Manager) -> None:
        """Reject token when signature or payload is modified."""
        res = oauth_manager._issue_token_response(
            client_id="agri-web-client",
            scopes=["agri:read"],
            subject="farmer_123",
        )
        token = res["access_token"]
        # Tamper token
        tampered = token[:-4] + "AAAA"
        token_info = await oauth_manager.verify_token(tampered)
        assert token_info is None

    @pytest.mark.anyio
    async def test_revoked_token_rejected(self, oauth_manager: OAuth2Manager) -> None:
        """Revoked tokens must not be accepted."""
        res = oauth_manager._issue_token_response(
            client_id="agri-web-client",
            scopes=["agri:read"],
            subject="farmer_123",
        )
        token = res["access_token"]

        assert await oauth_manager.verify_token(token) is not None
        oauth_manager.revoke_token(token)
        assert await oauth_manager.verify_token(token) is None

    @pytest.mark.anyio
    async def test_audience_mismatch_rejected(self, oauth_manager: OAuth2Manager) -> None:
        """Reject token when intended audience does not match server resource URL."""
        res = oauth_manager._issue_token_response(
            client_id="agri-web-client",
            scopes=["agri:read"],
            subject="farmer_123",
        )
        token = res["access_token"]
        # Intentionally alter expected resource_server_url on manager to simulate different audience
        oauth_manager.resource_server_url = "http://different-resource-server/mcp"
        token_info = await oauth_manager.verify_token(token)
        assert token_info is None

    def test_secret_sanitization(self) -> None:
        """Ensure tokens and secrets are redacted from diagnostic logs."""
        payload = {
            "client_id": "test",
            "client_secret": "my-secret-123",
            "access_token": "bearer.jwt.secret",
            "code": "authcode_123",
            "nested": {"refresh_token": "rt_123", "normal": "safe_value"},
        }
        cleaned = sanitize_secrets(payload)
        assert cleaned["client_secret"] == "***REDACTED***"
        assert cleaned["access_token"] == "***REDACTED***"
        assert cleaned["code"] == "***REDACTED***"
        assert cleaned["nested"]["refresh_token"] == "***REDACTED***"
        assert cleaned["nested"]["normal"] == "safe_value"


class TestRemoteStreamableHttpAuthMiddleware:
    """Test protection on the /mcp endpoint for remote Streamable HTTP."""

    def test_unauthenticated_mcp_request_rejected_401(self, test_client: TestClient) -> None:
        """Reject unauthenticated requests to /mcp with 401 Unauthorized and WWW-Authenticate header."""
        resp = test_client.get("/mcp")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers
        assert 'Bearer error="invalid_token"' in resp.headers["WWW-Authenticate"]
        data = resp.json()
        assert data["error"] == "invalid_token"

    def test_invalid_bearer_token_rejected_401(self, test_client: TestClient) -> None:
        """Reject requests with forged or invalid bearer token."""
        resp = test_client.get(
            "/mcp",
            headers={"Authorization": "Bearer forged-invalid-token-xyz"},
        )
        assert resp.status_code == 401
        assert "invalid_token" in resp.json()["error"]

    def test_authorized_mcp_request_accepted(self, test_client: TestClient) -> None:
        """Accept requests to /mcp with verified bearer token."""
        # Get demo token with agri:read
        token_resp = test_client.get("/api/oauth/demo-token?scope=agri:read")
        assert token_resp.status_code == 200
        token = token_resp.json()["token"]

        # Connect with bearer token
        resp = test_client.get(
            "/mcp",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Should not be 401 or 403 (it proceeds into the Starlette MCP application)
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_insufficient_scope_rejected_403(self, test_client: TestClient) -> None:
        """Token with empty/unrelated scopes rejected with 403 Forbidden."""
        from agricultural_assistant.server.oauth import oauth_manager

        res = oauth_manager._issue_token_response(
            client_id="agri-readonly-client",
            scopes=["other:unrelated"],
            subject="unauthorized_actor",
        )
        token = res["access_token"]

        resp = test_client.get(
            "/mcp",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "insufficient_scope"

    def test_unauthorized_write_rejected_403(self, test_client: TestClient) -> None:
        """Read-only token (agri:read) cannot execute write tools over Streamable HTTP."""
        from agricultural_assistant.server.oauth import oauth_manager

        res = oauth_manager._issue_token_response(
            client_id="agri-readonly-client",
            scopes=["agri:read"],
            subject="readonly_user",
        )
        token = res["access_token"]

        write_rpc = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "record_farm_observation",
                "arguments": {"crop": "Coffee", "notes": "Unauthorized write attempt"},
            },
        }

        resp = test_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {token}"},
            json=write_rpc,
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "insufficient_scope"
        assert "record_farm_observation" in resp.json()["error_description"]

    def test_authorized_write_accepted(self, test_client: TestClient) -> None:
        """Token with agri:write scope is accepted for write tool execution."""
        from agricultural_assistant.server.oauth import oauth_manager

        res = oauth_manager._issue_token_response(
            client_id="agri-evaluator-client",
            scopes=["agri:read", "agri:write"],
            subject="write_user",
        )
        token = res["access_token"]

        write_rpc = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "record_farm_observation",
                "arguments": {"crop": "Coffee", "notes": "Authorized write attempt note"},
            },
        }

        resp = test_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {token}"},
            json=write_rpc,
        )
        # Should not be 401 or 403 (it is accepted by authorization middleware)
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_demo_token_disabled_in_production(self) -> None:
        """The development /demo-token endpoint is strictly disabled when APP_ENV=production."""
        prod_app = create_app(settings=Settings(app_env="production"))
        with TestClient(prod_app) as client:
            resp = client.get("/api/oauth/demo-token")
            assert resp.status_code == 403
            assert "disabled in production mode" in resp.json()["detail"]
