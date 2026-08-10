"""
Plugin Execution Context
========================
Passed to every action and trigger handler. Provides access to
configuration, secrets, the HTTP client, logging, and metadata.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class PluginContext:
    """
    Runtime context injected into every plugin call.
    Plugins must NOT import secrets directly — use ctx.secret().
    """
    plugin_id:  str
    run_id:     str
    node_id:    str
    config:     Dict[str, Any]         = field(default_factory=dict)
    _secrets:   Dict[str, str]         = field(default_factory=dict, repr=False)
    dry_run:    bool                   = False
    metadata:   Dict[str, Any]         = field(default_factory=dict)
    _logger:    Optional[logging.Logger] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._logger is None:
            self._logger = logging.getLogger(f"plugin.{self.plugin_id}")

    # ------------------------------------------------------------------
    # Secret access — never logged, never serialised
    # ------------------------------------------------------------------

    def secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a secret by env-var name."""
        import os
        return self._secrets.get(key) or os.environ.get(key, default)

    def require_secret(self, key: str) -> str:
        """Retrieve a required secret, raising ConfigError if missing."""
        from plugins.sdk.errors import ConfigError
        val = self.secret(key)
        if not val:
            raise ConfigError(f"Required secret '{key}' is not configured", field=key)
        return val

    # ------------------------------------------------------------------
    # Config access
    # ------------------------------------------------------------------

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def require_config(self, key: str) -> Any:
        from plugins.sdk.errors import ConfigError
        val = self.config.get(key)
        if val is None:
            raise ConfigError(f"Required config '{key}' is not set", field=key)
        return val

    # ------------------------------------------------------------------
    # Structured logging helpers
    # ------------------------------------------------------------------

    def log(self, message: str, level: str = "info", **kw: Any) -> None:
        getattr(self._logger, level, self._logger.info)(
            "[%s/%s] %s", self.plugin_id, self.node_id, message
        )

    def debug(self, msg: str, **kw: Any) -> None:   self.log(msg, "debug")
    def info(self, msg: str, **kw: Any) -> None:    self.log(msg, "info")
    def warning(self, msg: str, **kw: Any) -> None: self.log(msg, "warning")
    def error(self, msg: str, **kw: Any) -> None:   self.log(msg, "error")

    # ------------------------------------------------------------------
    # HTTP helpers (thin wrapper around httpx)
    # ------------------------------------------------------------------

    def http_get(self, url: str, **kw: Any) -> Any:
        return self._http("GET", url, **kw)

    def http_post(self, url: str, **kw: Any) -> Any:
        return self._http("POST", url, **kw)

    def http_put(self, url: str, **kw: Any) -> Any:
        return self._http("PUT", url, **kw)

    def http_patch(self, url: str, **kw: Any) -> Any:
        return self._http("PATCH", url, **kw)

    def http_delete(self, url: str, **kw: Any) -> Any:
        return self._http("DELETE", url, **kw)

    def _http(self, method: str, url: str, **kw: Any) -> Any:
        from plugins.sdk.errors import NetworkError, RateLimitError
        if self.dry_run:
            self._logger.info("[DRY-RUN] HTTP %s %s", method, url)
            return {"simulated": True, "url": url, "method": method}
        try:
            import httpx
            with httpx.Client(timeout=30) as client:
                resp = client.request(method, url, **kw)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after=retry_after)
                resp.raise_for_status()
                try:
                    return resp.json()
                except Exception:
                    return resp.text
        except (RateLimitError, NetworkError):
            raise
        except Exception as exc:
            raise NetworkError(str(exc)) from exc
