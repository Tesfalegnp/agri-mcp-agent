"""OAuth 2.1 Authorization Server, Token Verifier, and Scope Enforcement.

Implements the official OAuth 2.1 protocol for securing remote MCP Streamable HTTP endpoints.
Features:
- Authorization Code Flow with PKCE (RFC 7636, S256 & plain).
- Client Credentials Grant for machine-to-machine integrations.
- Cryptographically verified HMAC-SHA256 Bearer tokens.
- Token introspection (RFC 7662), revocation (RFC 7009), and Authorization Server Metadata (RFC 8414).
- MCP SDK `TokenVerifier` protocol compatibility (`mcp.server.auth.provider.AccessToken`).
- Scoped permissions: `agri:read` (read-only diagnostics/weather/knowledge) and `agri:write` (field observation persistence).
- Protection against unauthorized writes from read-only tokens.
- Zero logging of access tokens, client secrets, or authorization codes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from mcp.server.auth.provider import AccessToken
from pydantic import BaseModel, Field

logger = logging.getLogger("agricultural_assistant.oauth")

# Sensitive parameter names that must NEVER appear in logs or errors
SENSITIVE_PARAM_NAMES = {"client_secret", "code", "code_verifier", "access_token", "refresh_token", "token"}


def sanitize_secrets(data: Any) -> Any:
    """Recursively mask tokens, secrets, and authorization codes."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if any(s in k.lower() for s in SENSITIVE_PARAM_NAMES):
                cleaned[k] = "***REDACTED***"
            else:
                cleaned[k] = sanitize_secrets(v)
        return cleaned
    elif isinstance(data, list):
        return [sanitize_secrets(x) for x in data]
    return data


class RegisteredClient(BaseModel):
    """Configuration contract for a registered OAuth 2.1 client."""
    client_id: str
    client_name: str
    client_type: str = "public"  # "public" (PKCE required) or "confidential" (client_secret required)
    client_secret_hash: Optional[str] = None
    redirect_uris: List[str] = Field(default_factory=list)
    allowed_scopes: List[str] = Field(default_factory=lambda: ["agri:read", "agri:write"])
    require_pkce: bool = True


class AuthorizationCodeRecord(BaseModel):
    """In-memory record for a single-use authorization code with PKCE."""
    code: str
    client_id: str
    redirect_uri: str
    scope: str
    code_challenge: str
    code_challenge_method: str = "S256"
    expires_at: float
    used: bool = False


class OAuth2Manager:
    """OAuth 2.1 Authorization Server and Token Verifier."""

    def __init__(
        self,
        issuer: Optional[str] = None,
        jwt_secret: Optional[str] = None,
        resource_server_url: Optional[str] = None,
        token_lifetime_seconds: int = 3600,
        auth_code_lifetime_seconds: int = 600,
    ) -> None:
        self.issuer = issuer or os.getenv("OAUTH_ISSUER", "http://127.0.0.1:8000")
        self.resource_server_url = resource_server_url or os.getenv("OAUTH_RESOURCE_URL", "http://127.0.0.1:8000/mcp")
        self.jwt_secret = jwt_secret or os.getenv("OAUTH_SECRET_KEY") or "agri-mcp-oauth2-super-secret-key-2026-production"
        self.token_lifetime_seconds = token_lifetime_seconds
        self.auth_code_lifetime_seconds = auth_code_lifetime_seconds

        # In-memory storage for codes and revoked tokens
        self._auth_codes: Dict[str, AuthorizationCodeRecord] = {}
        self._revoked_tokens: Set[str] = set()

        # Pre-registered OAuth 2.1 clients
        self._clients: Dict[str, RegisteredClient] = {}
        self._register_default_clients()

    def _register_default_clients(self) -> None:
        """Register default client profiles for Evaluator demonstration and testing."""
        # 1. Public Web Client (PKCE required, no client_secret stored in browser)
        self.register_client(
            RegisteredClient(
                client_id="agri-web-client",
                client_name="Agricultural Web UI Client",
                client_type="public",
                redirect_uris=[
                    "http://localhost:5173/oauth/callback",
                    "http://127.0.0.1:5173/oauth/callback",
                    "http://localhost:8000/oauth/callback",
                    "http://127.0.0.1:8000/oauth/callback",
                ],
                allowed_scopes=["agri:read", "agri:write"],
                require_pkce=True,
            )
        )

        # 2. Confidential Evaluator Service (client_secret = "evaluator-secret-key-2026")
        evaluator_secret = os.getenv("OAUTH_EVALUATOR_SECRET", "evaluator-secret-key-2026")
        self.register_client(
            RegisteredClient(
                client_id="agri-evaluator-client",
                client_name="Agricultural Evaluator Machine Client",
                client_type="confidential",
                client_secret_hash=self._hash_secret(evaluator_secret),
                allowed_scopes=["agri:read", "agri:write"],
                require_pkce=False,
            )
        )

        # 3. Read-Only Scout Client (Demonstrates scope gating: cannot execute write tools)
        readonly_secret = os.getenv("OAUTH_READONLY_SECRET", "readonly-secret-key-2026")
        self.register_client(
            RegisteredClient(
                client_id="agri-readonly-client",
                client_name="Agricultural Read-Only Client",
                client_type="confidential",
                client_secret_hash=self._hash_secret(readonly_secret),
                allowed_scopes=["agri:read"],
                require_pkce=False,
            )
        )

    @staticmethod
    def _hash_secret(secret: str) -> str:
        """Compute SHA-256 hash of client secret."""
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    def register_client(self, client: RegisteredClient) -> None:
        """Register a new OAuth client."""
        self._clients[client.client_id] = client

    def get_client(self, client_id: str) -> Optional[RegisteredClient]:
        """Look up a client by ID."""
        return self._clients.get(client_id)

    # --- PKCE Verification ---

    @staticmethod
    def verify_pkce(code_verifier: str, code_challenge: str, method: str = "S256") -> bool:
        """Verify code_verifier against code_challenge according to RFC 7636."""
        if not code_verifier or not code_challenge:
            return False

        if method == "S256":
            digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
            calculated = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
            return hmac.compare_digest(calculated, code_challenge)
        elif method == "plain":
            return hmac.compare_digest(code_verifier, code_challenge)
        return False

    # --- Authorization Code Grant ---

    def create_authorization_code(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str,
        code_challenge: str,
        code_challenge_method: str = "S256",
    ) -> str:
        """Issue a short-lived authorization code associated with PKCE challenge."""
        client = self.get_client(client_id)
        if not client:
            raise ValueError(f"Unknown client_id: '{client_id}'")

        if client.require_pkce and not code_challenge:
            raise ValueError("PKCE code_challenge is required for public OAuth 2.1 clients.")

        # Validate redirect_uri against client's pre-registered URIs
        if client.redirect_uris and redirect_uri not in client.redirect_uris:
            raise ValueError(
                f"Invalid redirect_uri '{redirect_uri}'. Not in registered redirect_uris for client '{client_id}'."
            )

        # Validate requested scope
        requested_scopes = set(scope.split()) if scope else {"agri:read"}
        allowed = set(client.allowed_scopes)
        if not requested_scopes.issubset(allowed):
            raise ValueError(f"Requested scopes {requested_scopes} exceed allowed scopes {allowed}")

        code = f"authcode_{secrets.token_urlsafe(32)}"
        record = AuthorizationCodeRecord(
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=" ".join(sorted(requested_scopes)),
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=time.time() + self.auth_code_lifetime_seconds,
            used=False,
        )
        self._auth_codes[code] = record
        return code

    def exchange_authorization_code(
        self,
        code: str,
        client_id: str,
        code_verifier: str,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exchange an authorization code and PKCE verifier for an access token."""
        record = self._auth_codes.get(code)
        if not record:
            raise ValueError("Invalid authorization code.")

        if record.used:
            # Possible code reuse attack: revoke all tokens if possible
            del self._auth_codes[code]
            raise ValueError("Authorization code was already used. Potential replay detected.")

        if time.time() > record.expires_at:
            del self._auth_codes[code]
            raise ValueError("Authorization code has expired.")

        if record.client_id != client_id:
            raise ValueError("client_id does not match authorization code issuer.")

        if redirect_uri and record.redirect_uri and redirect_uri != record.redirect_uri:
            raise ValueError("redirect_uri does not match original authorization request.")

        # Validate PKCE
        if not self.verify_pkce(code_verifier, record.code_challenge, record.code_challenge_method):
            raise ValueError("Invalid PKCE code_verifier.")

        record.used = True
        del self._auth_codes[code]

        # Issue access token
        return self._issue_token_response(
            client_id=client_id,
            scopes=record.scope.split(),
            subject=f"user_{client_id}",
        )

    # --- Client Credentials Grant ---

    def exchange_client_credentials(
        self,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exchange client credentials for an access token."""
        client = self.get_client(client_id)
        if not client or client.client_type != "confidential":
            raise ValueError("Invalid client credentials.")

        if not client.client_secret_hash:
            raise ValueError("Client has no secret configured.")

        expected_hash = client.client_secret_hash
        actual_hash = self._hash_secret(client_secret)
        if not hmac.compare_digest(expected_hash, actual_hash):
            raise ValueError("Invalid client credentials.")

        requested_scopes = set(scope.split()) if scope else set(client.allowed_scopes)
        allowed = set(client.allowed_scopes)
        granted_scopes = list(requested_scopes.intersection(allowed))
        if not granted_scopes:
            granted_scopes = ["agri:read"]

        return self._issue_token_response(
            client_id=client_id,
            scopes=granted_scopes,
            subject=f"service_{client_id}",
        )

    # --- Token Generation & Cryptographic Signing ---

    def _issue_token_response(
        self,
        client_id: str,
        scopes: List[str],
        subject: str,
    ) -> Dict[str, Any]:
        """Generate a signed Bearer token with claims."""
        now = int(time.time())
        expires_at = now + self.token_lifetime_seconds

        payload = {
            "iss": self.issuer,
            "aud": self.resource_server_url,
            "sub": subject,
            "client_id": client_id,
            "scope": " ".join(scopes),
            "iat": now,
            "exp": expires_at,
            "jti": secrets.token_hex(16),
        }

        token = self._sign_payload(payload)

        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self.token_lifetime_seconds,
            "scope": " ".join(scopes),
            "issued_at": now,
        }

    def _sign_payload(self, payload: Dict[str, Any]) -> str:
        """Create a tamper-proof HMAC-SHA256 signed bearer token."""
        header = {"alg": "HS256", "typ": "JWT"}
        b64_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

        signing_input = f"{b64_header}.{b64_payload}"
        signature = hmac.new(
            self.jwt_secret.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        b64_sig = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        return f"{signing_input}.{b64_sig}"

    # --- Token Verification (MCP SDK Protocol) ---

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """Verify bearer token and return AccessToken if valid, conforming to MCP TokenVerifier."""
        if not token or token in self._revoked_tokens:
            return None

        parts = token.split(".")
        if len(parts) != 3:
            return None

        b64_header, b64_payload, b64_sig = parts
        signing_input = f"{b64_header}.{b64_payload}"

        # Verify HMAC signature
        expected_sig = hmac.new(
            self.jwt_secret.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected_b64_sig = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")

        if not hmac.compare_digest(expected_b64_sig, b64_sig):
            logger.warning("Token verification failed: invalid HMAC signature.")
            return None

        # Decode payload
        try:
            # Re-pad base64
            padded_payload = b64_payload + "=" * (-len(b64_payload) % 4)
            payload_bytes = base64.urlsafe_b64decode(padded_payload)
            payload = json.loads(payload_bytes.decode("utf-8"))
        except Exception as exc:
            logger.warning("Token verification failed: malformed payload (%s)", exc)
            return None

        # Check expiration
        exp = payload.get("exp")
        if exp is not None and time.time() > exp:
            logger.warning("Token verification failed: token has expired.")
            return None

        # Check issuer
        iss = payload.get("iss")
        if iss and self.issuer and iss != self.issuer:
            logger.warning("Token verification failed: issuer mismatch (%s != %s)", iss, self.issuer)
            return None

        # Check audience / resource
        aud = payload.get("aud")
        if aud and self.resource_server_url and aud != self.resource_server_url:
            logger.warning("Token verification failed: audience mismatch (%s != %s)", aud, self.resource_server_url)
            return None

        scopes = payload.get("scope", "").split() if payload.get("scope") else ["agri:read"]
        client_id = payload.get("client_id", "unknown_client")
        subject = payload.get("sub")
        resource = payload.get("aud")

        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=exp,
            resource=resource,
            subject=subject,
            claims=payload,
        )

    # --- Introspection and Revocation ---

    async def introspect_token(self, token: str) -> Dict[str, Any]:
        """Introspect a token according to RFC 7662."""
        token_info = await self.verify_token(token)
        if not token_info:
            return {"active": False}

        claims = token_info.claims or {}
        return {
            "active": True,
            "scope": " ".join(token_info.scopes),
            "client_id": token_info.client_id,
            "sub": token_info.subject,
            "aud": token_info.resource,
            "iss": claims.get("iss"),
            "exp": token_info.expires_at,
            "iat": claims.get("iat"),
            "token_type": "Bearer",
        }

    def revoke_token(self, token: str) -> bool:
        """Revoke a token according to RFC 7009."""
        if token:
            self._revoked_tokens.add(token)
            return True
        return False

    def get_metadata(self) -> Dict[str, Any]:
        """Return OAuth 2.1 Authorization Server Metadata (RFC 8414)."""
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{self.issuer}/api/oauth/authorize",
            "token_endpoint": f"{self.issuer}/api/oauth/token",
            "introspection_endpoint": f"{self.issuer}/api/oauth/introspect",
            "revocation_endpoint": f"{self.issuer}/api/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "client_credentials"],
            "code_challenge_methods_supported": ["S256", "plain"],
            "scopes_supported": ["agri:read", "agri:write"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
            "service_documentation": "https://github.com/Tesfalegnp/agri-mcp-agent",
        }


# Singleton OAuth Manager
oauth_manager = OAuth2Manager()
