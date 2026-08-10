"""
BasePlugin
==========
Abstract base class that every plugin must subclass.
Provides the plugin lifecycle interface, introspection utilities,
and the execute_action / poll_trigger dispatch methods.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from plugins.sdk.manifest import PluginManifest
from plugins.sdk.context import PluginContext
from plugins.sdk.result import ActionResult, TriggerEvent
from plugins.sdk.auth import AuthProvider, NoAuthProvider, Credentials

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """
    Every plugin must:
      1. Subclass BasePlugin
      2. Define a `manifest` class attribute (PluginManifest instance)
      3. Implement `execute_action(action_id, ctx, params)`
      4. Optionally implement `poll_trigger(trigger_id, ctx, since)`

    Lifecycle hooks (on_install, on_uninstall, on_configure, on_enable, on_disable)
    may be overridden for custom setup/teardown logic.

    The plugin class MUST be named `Plugin` inside its plugin.py file.
    """

    # Subclasses set this as a class attribute
    manifest: PluginManifest

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def get_auth_provider(self) -> AuthProvider:
        """
        Return the auth provider for this plugin.
        Override to supply custom OAuth, API key, or Basic auth providers.
        """
        return NoAuthProvider()

    def authenticate(self, config: Dict[str, Any], secrets: Dict[str, str]) -> Credentials:
        """Resolve credentials using this plugin's auth provider."""
        return self.get_auth_provider().authenticate(config, secrets)

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    @abstractmethod
    def execute_action(
        self,
        action_id: str,
        ctx:       PluginContext,
        params:    Dict[str, Any],
    ) -> ActionResult:
        """
        Dispatch an action call to the appropriate handler method.
        Subclasses should route by action_id to specific methods.

        Raises:
            PluginError: on any plugin-specific error
            ValidationError: if params are invalid
        """
        ...

    # ------------------------------------------------------------------
    # Trigger polling
    # ------------------------------------------------------------------

    def poll_trigger(
        self,
        trigger_id: str,
        ctx:        PluginContext,
        since:      Optional[Any] = None,
    ) -> List[TriggerEvent]:
        """
        Poll for new trigger events since `since`.
        Returns a (possibly empty) list of TriggerEvent objects.
        Override for polling-based triggers.
        """
        return []

    # ------------------------------------------------------------------
    # Webhook handling
    # ------------------------------------------------------------------

    def handle_webhook(
        self,
        trigger_id: str,
        ctx:        PluginContext,
        payload:    Dict[str, Any],
        headers:    Dict[str, str],
    ) -> List[TriggerEvent]:
        """
        Process an incoming webhook payload for the given trigger.
        Override for webhook-based triggers.
        """
        return []

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate user-supplied configuration.
        Returns a list of error strings (empty = valid).
        """
        from plugins.sdk.validators import PluginValidator
        return PluginValidator.validate_config(self.manifest.config, config)

    def validate_action_params(self, action_id: str, params: Dict[str, Any]) -> List[str]:
        """Validate action input params against the action's schema."""
        from plugins.sdk.validators import PluginValidator
        return PluginValidator.validate_action_input(self.manifest, action_id, params)

    # ------------------------------------------------------------------
    # Lifecycle hooks (optional overrides)
    # ------------------------------------------------------------------

    def on_install(self, ctx: PluginContext) -> None:
        """Called after the plugin is installed. Use for one-time setup."""
        logger.info("Plugin '%s' installed.", self.manifest.id)

    def on_uninstall(self, ctx: PluginContext) -> None:
        """Called before the plugin is removed. Use for cleanup."""
        logger.info("Plugin '%s' uninstalled.", self.manifest.id)

    def on_enable(self, ctx: PluginContext) -> None:
        """Called when the plugin is enabled."""
        logger.info("Plugin '%s' enabled.", self.manifest.id)

    def on_disable(self, ctx: PluginContext) -> None:
        """Called when the plugin is disabled."""
        logger.info("Plugin '%s' disabled.", self.manifest.id)

    def on_configure(self, ctx: PluginContext, config: Dict[str, Any]) -> None:
        """Called after configuration is saved."""
        logger.info("Plugin '%s' configured.", self.manifest.id)

    def on_test(self, ctx: PluginContext) -> ActionResult:
        """
        Connection test — called from the UI when user clicks 'Test Connection'.
        Default implementation returns a success stub.
        """
        return ActionResult.ok(data={"message": f"Plugin '{self.manifest.name}' is reachable."})

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        """Return the full manifest as a dict."""
        return self.manifest.to_dict()

    def __repr__(self) -> str:
        return f"<Plugin id={self.manifest.id!r} version={self.manifest.version!r}>"
