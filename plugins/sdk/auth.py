"""Plugin authentication providers."""
from __future__ import annotations

import base64
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Credentials:
    """Resolved, ready-to-use credentials."""
    token:      Optional[str]   = None
    headers:    Dict[str, str]  = field(default_factory=dict)
    expires_at: Optional[float] = None   # Unix timestamp
    raw:        Dict[str, Any]  = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at

    def bearer_header(self) -> Dict[str, str]:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}


class AuthProvider(ABC):
    """Abstract base class for all auth providers."""

    @abstractmethod
    def authenticate(self, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials: ...

    @abstractmethod
    def refresh(self, credentials: Credentials, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials: ...

    def get_headers(self, credentials: Credentials) -> Dict[str, str]:
        return credentials.headers


class NoAuthProvider(AuthProvider):
    """No authentication required."""
    def authenticate(self, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials:
        return Credentials()

    def refresh(self, credentials: Credentials, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials:
        return Credentials()


class ApiKeyProvider(AuthProvider):
    """Simple API-key authentication via a header."""
    def __init__(self, secret_key: str, header_name: str = "X-API-Key", prefix: str = "") -> None:
        self.secret_key  = secret_key
        self.header_name = header_name
        self.prefix      = prefix

    def authenticate(self, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials:
        from plugins.sdk.errors import AuthError
        key = secrets.get(self.secret_key) or os.environ.get(self.secret_key)
        if not key:
            raise AuthError(f"Missing API key: {self.secret_key}")
        value = f"{self.prefix}{key}" if self.prefix else key
        return Credentials(token=key, headers={self.header_name: value})

    def refresh(self, credentials: Credentials, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials:
        return self.authenticate(config, secrets)


class BearerTokenProvider(AuthProvider):
    """Bearer token authentication (Authorization: Bearer <token>)."""
    def __init__(self, secret_key: str) -> None:
        self.secret_key = secret_key

    def authenticate(self, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials:
        from plugins.sdk.errors import AuthError
        token = secrets.get(self.secret_key) or os.environ.get(self.secret_key)
        if not token:
            raise AuthError(f"Missing bearer token: {self.secret_key}")
        return Credentials(token=token, headers={"Authorization": f"Bearer {token}"})

    def refresh(self, credentials: Credentials, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials:
        return self.authenticate(config, secrets)


class BasicAuthProvider(AuthProvider):
    """HTTP Basic authentication (username:password)."""
    def __init__(self, username_key: str, password_key: str) -> None:
        self.username_key = username_key
        self.password_key = password_key

    def authenticate(self, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials:
        from plugins.sdk.errors import AuthError
        username = secrets.get(self.username_key) or config.get("username") or ""
        password = secrets.get(self.password_key) or ""
        if not username or not password:
            raise AuthError("Missing username or password for Basic auth")
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return Credentials(headers={"Authorization": f"Basic {encoded}"})

    def refresh(self, credentials: Credentials, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials:
        return self.authenticate(config, secrets)


class OAuthProvider(AuthProvider):
    """OAuth 2.0 Client-Credentials flow with automatic token refresh."""
    def __init__(
        self,
        client_id_key:     str,
        client_secret_key: str,
        token_url:         str,
        scopes:            Optional[List[str]] = None,
    ) -> None:
        self.client_id_key     = client_id_key
        self.client_secret_key = client_secret_key
        self.token_url         = token_url
        self.scopes            = scopes or []

    def authenticate(self, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials:
        from plugins.sdk.errors import AuthError, NetworkError
        client_id     = secrets.get(self.client_id_key)     or os.environ.get(self.client_id_key)
        client_secret = secrets.get(self.client_secret_key) or os.environ.get(self.client_secret_key)
        if not client_id or not client_secret:
            raise AuthError("Missing OAuth client_id or client_secret")
        try:
            import httpx
            data: Dict[str, str] = {
                "grant_type":    "client_credentials",
                "client_id":     client_id,
                "client_secret": client_secret,
            }
            if self.scopes:
                data["scope"] = " ".join(self.scopes)
            with httpx.Client(timeout=15) as client:
                resp = client.post(self.token_url, data=data)
                resp.raise_for_status()
                body = resp.json()
            expires_in = body.get("expires_in", 3600)
            return Credentials(
                token=body["access_token"],
                headers={"Authorization": f"Bearer {body['access_token']}"},
                expires_at=time.time() + expires_in - 60,
                raw=body,
            )
        except Exception as exc:
            raise NetworkError(f"OAuth token request failed: {exc}") from exc

    def refresh(self, credentials: Credentials, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials:
        # Re-authenticate for client-credentials (stateless)
        return self.authenticate(config, secrets)
