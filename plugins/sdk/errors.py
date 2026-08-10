"""Plugin system error hierarchy."""
from __future__ import annotations
from typing import Optional, Dict, Any


class PluginError(Exception):
    """Base class for all plugin errors."""
    def __init__(
        self,
        message: str,
        code: str = "PLUGIN_ERROR",
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message   = message
        self.code      = code
        self.details   = details or {}
        self.retryable = retryable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error":     self.code,
            "message":   self.message,
            "details":   self.details,
            "retryable": self.retryable,
        }


class AuthError(PluginError):
    """Authentication / authorisation failure."""
    def __init__(self, message: str = "Authentication failed", **kw: Any) -> None:
        super().__init__(message, code="AUTH_ERROR", **kw)


class ConfigError(PluginError):
    """Plugin misconfiguration."""
    def __init__(self, message: str, field: Optional[str] = None, **kw: Any) -> None:
        details = kw.pop("details", {})
        if field:
            details["field"] = field
        super().__init__(message, code="CONFIG_ERROR", details=details, **kw)


class ValidationError(PluginError):
    """Input validation failure."""
    def __init__(self, message: str, errors: Optional[list] = None, **kw: Any) -> None:
        details = {"errors": errors or []}
        super().__init__(message, code="VALIDATION_ERROR", details=details, **kw)


class RateLimitError(PluginError):
    """API rate limit exceeded."""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None, **kw: Any) -> None:
        details: Dict[str, Any] = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(message, code="RATE_LIMIT", details=details, retryable=True, **kw)


class NetworkError(PluginError):
    """Network / connectivity failure."""
    def __init__(self, message: str = "Network error", **kw: Any) -> None:
        super().__init__(message, code="NETWORK_ERROR", retryable=True, **kw)


class NotFoundError(PluginError):
    """Requested resource not found."""
    def __init__(self, resource: str, **kw: Any) -> None:
        super().__init__(f"Resource not found: {resource}", code="NOT_FOUND", **kw)


class PluginPermissionError(PluginError):
    """Insufficient permissions for the requested operation."""
    def __init__(self, scope: str, **kw: Any) -> None:
        super().__init__(f"Permission denied: {scope}", code="PERMISSION_DENIED", **kw)
