"""Plugin SDK — public surface."""
from plugins.sdk.base import BasePlugin
from plugins.sdk.manifest import (
    PluginManifest, AuthConfig, TriggerSpec, ActionSpec,
    TriggerOutputField, ActionInputField, ConfigField, Permission, LifecycleHook,
)
from plugins.sdk.registry import PluginRegistry
from plugins.sdk.auth import (
    AuthProvider, OAuthProvider, ApiKeyProvider,
    BasicAuthProvider, BearerTokenProvider, NoAuthProvider, Credentials,
)
from plugins.sdk.context import PluginContext
from plugins.sdk.result import ActionResult, TriggerEvent
from plugins.sdk.errors import (
    PluginError, AuthError, ConfigError, ValidationError,
    RateLimitError, NetworkError, NotFoundError, PluginPermissionError,
)
from plugins.sdk.validators import PluginValidator
from plugins.sdk.decorators import action, trigger, on_install, on_uninstall, on_configure
from plugins.sdk.enums import (
    AuthType, FieldType, TriggerType, PermissionScope, PluginStatus, LifecycleEvent,
)

__all__ = [
    # Core
    "BasePlugin", "PluginManifest", "PluginRegistry",
    # Manifest building blocks
    "AuthConfig", "TriggerSpec", "ActionSpec", "TriggerOutputField",
    "ActionInputField", "ConfigField", "Permission", "LifecycleHook",
    # Auth
    "AuthProvider", "OAuthProvider", "ApiKeyProvider",
    "BasicAuthProvider", "BearerTokenProvider", "NoAuthProvider", "Credentials",
    # Runtime
    "PluginContext", "ActionResult", "TriggerEvent",
    # Errors
    "PluginError", "AuthError", "ConfigError", "ValidationError",
    "RateLimitError", "NetworkError", "NotFoundError", "PluginPermissionError",
    # Utils
    "PluginValidator",
    # Decorators
    "action", "trigger", "on_install", "on_uninstall", "on_configure",
    # Enums
    "AuthType", "FieldType", "TriggerType", "PermissionScope", "PluginStatus", "LifecycleEvent",
]
