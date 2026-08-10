"""
Plugin Manifest
===============
The single source of truth for a plugin's identity, capabilities,
authentication requirements, triggers, actions, and configuration schema.
Every plugin MUST define a PluginManifest instance as a class attribute.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from plugins.sdk.enums import AuthType, FieldType, TriggerType, PermissionScope, LifecycleEvent


# ---------------------------------------------------------------------------
# Configuration Field
# ---------------------------------------------------------------------------

@dataclass
class ConfigField:
    """
    Describes one configuration field that the user must fill in
    when installing / configuring a plugin.
    """
    name:        str
    label:       str
    type:        FieldType           = FieldType.STRING
    required:    bool                = True
    sensitive:   bool                = False      # masked in logs & UI
    default:     Any                 = None
    placeholder: Optional[str]       = None
    help_text:   Optional[str]       = None
    options:     Optional[List[str]] = None       # for SELECT / MULTI
    min_length:  Optional[int]       = None
    max_length:  Optional[int]       = None
    pattern:     Optional[str]       = None       # regex validation
    depends_on:  Optional[str]       = None       # only show when this field has a value
    group:       Optional[str]       = None       # visual grouping label

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":        self.name,
            "label":       self.label,
            "type":        self.type.value,
            "required":    self.required,
            "sensitive":   self.sensitive,
            "default":     self.default,
            "placeholder": self.placeholder,
            "help_text":   self.help_text,
            "options":     self.options,
            "depends_on":  self.depends_on,
            "group":       self.group,
        }


# ---------------------------------------------------------------------------
# Authentication Config
# ---------------------------------------------------------------------------

@dataclass
class AuthConfig:
    """
    Describes how the plugin authenticates with the external service.
    """
    type:                AuthType
    label:               str           = "Connect Account"
    # OAuth2 fields
    oauth_authorize_url: Optional[str] = None
    oauth_token_url:     Optional[str] = None
    oauth_scopes:        List[str]     = field(default_factory=list)
    oauth_client_id_env: Optional[str] = None    # env var holding client ID
    # API Key fields
    api_key_header:      Optional[str] = None
    api_key_prefix:      Optional[str] = None    # e.g. "Bearer "
    api_key_env:         Optional[str] = None    # env var name
    # Documentation
    help_url:            Optional[str] = None
    help_text:           Optional[str] = None
    setup_steps:         List[str]     = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type":                self.type.value,
            "label":               self.label,
            "oauth_scopes":        self.oauth_scopes,
            "oauth_authorize_url": self.oauth_authorize_url,
            "api_key_header":      self.api_key_header,
            "help_url":            self.help_url,
            "setup_steps":         self.setup_steps,
        }


# ---------------------------------------------------------------------------
# Trigger Spec
# ---------------------------------------------------------------------------

@dataclass
class TriggerOutputField:
    name:        str
    type:        str
    description: str
    example:     Any = None


@dataclass
class TriggerSpec:
    """
    Describes one trigger that this plugin can emit.
    """
    id:          str
    name:        str
    description: str
    type:        TriggerType
    # Polling-specific
    poll_interval_seconds: Optional[int]             = 60
    # Webhook-specific
    webhook_path:          Optional[str]             = None
    # Output schema
    output_fields:         List[TriggerOutputField]  = field(default_factory=list)
    # Docs & UX
    icon:                  Optional[str]             = None
    docs_url:              Optional[str]             = None
    example_payload:       Optional[Dict[str, Any]]  = None
    deprecated:            bool                      = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":          self.id,
            "name":        self.name,
            "description": self.description,
            "type":        self.type.value,
            "icon":        self.icon,
            "deprecated":  self.deprecated,
            "output_fields": [vars(f) for f in self.output_fields],
        }


# ---------------------------------------------------------------------------
# Action Spec
# ---------------------------------------------------------------------------

@dataclass
class ActionInputField:
    name:        str
    type:        str
    description: str
    required:    bool = True
    default:     Any  = None
    example:     Any  = None
    options:     Optional[List[str]] = None


@dataclass
class ActionSpec:
    """
    Describes one action that this plugin can perform.
    """
    id:          str
    name:        str
    description: str
    # I/O schema
    input_fields:  List[ActionInputField]   = field(default_factory=list)
    output_fields: List[TriggerOutputField] = field(default_factory=list)
    # Behaviour
    idempotent:  bool                       = False
    readonly:    bool                       = False
    # UX
    icon:        Optional[str]              = None
    docs_url:    Optional[str]              = None
    example:     Optional[Dict[str, Any]]   = None
    deprecated:  bool                       = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":           self.id,
            "name":         self.name,
            "description":  self.description,
            "idempotent":   self.idempotent,
            "readonly":     self.readonly,
            "deprecated":   self.deprecated,
            "input_fields": [vars(f) for f in self.input_fields],
            "output_fields":[vars(f) for f in self.output_fields],
        }


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------

@dataclass
class Permission:
    """
    Declares what the plugin is allowed to access/modify.
    Users see this list during the install / consent flow.
    """
    scope:       PermissionScope
    resource:    str             # e.g. "spreadsheets", "messages"
    description: str
    required:    bool            = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope":       self.scope.value,
            "resource":    self.resource,
            "description": self.description,
            "required":    self.required,
        }


# ---------------------------------------------------------------------------
# Lifecycle Hook
# ---------------------------------------------------------------------------

@dataclass
class LifecycleHook:
    """
    Declares a lifecycle event handler method name on the plugin class.
    """
    event:       LifecycleEvent
    method_name: str
    description: str = ""


# ---------------------------------------------------------------------------
# Plugin Manifest — the plugin's "passport"
# ---------------------------------------------------------------------------

@dataclass
class PluginManifest:
    """
    The complete identity and capability declaration for a plugin.
    This is validated on install and introspected by the UI and engine.
    """
    # ---- Identity --------------------------------------------------------
    id:          str               # e.g. "google_sheets" — unique, snake_case
    name:        str               # e.g. "Google Sheets"
    version:     str               # SemVer: "1.2.0"
    description: str
    author:      str
    homepage:    Optional[str]     = None
    docs_url:    Optional[str]     = None
    support_url: Optional[str]     = None
    changelog:   Optional[str]     = None
    license:     str               = "MIT"

    # ---- Visuals ---------------------------------------------------------
    icon:        Optional[str]     = None   # URL, emoji, or base64 SVG
    icon_bg:     Optional[str]     = None   # background hex color e.g. "#4285F4"
    color:       Optional[str]     = None   # brand hex color

    # ---- Discovery -------------------------------------------------------
    categories:  List[str]         = field(default_factory=list)
    tags:        List[str]         = field(default_factory=list)

    # ---- Capabilities ----------------------------------------------------
    auth:        Optional[AuthConfig]   = None
    triggers:    List[TriggerSpec]      = field(default_factory=list)
    actions:     List[ActionSpec]       = field(default_factory=list)
    config:      List[ConfigField]      = field(default_factory=list)
    permissions: List[Permission]       = field(default_factory=list)
    lifecycle:   List[LifecycleHook]    = field(default_factory=list)

    # ---- Compatibility ---------------------------------------------------
    min_engine_version: str             = "1.0.0"
    python_requires:    str             = ">=3.10"
    dependencies:       List[str]       = field(default_factory=list)  # pip packages

    # ---- Status ----------------------------------------------------------
    beta:             bool              = False
    deprecated:       bool              = False
    deprecated_reason: Optional[str]   = None

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def get_trigger(self, trigger_id: str) -> Optional[TriggerSpec]:
        return next((t for t in self.triggers if t.id == trigger_id), None)

    def get_action(self, action_id: str) -> Optional[ActionSpec]:
        return next((a for a in self.actions if a.id == action_id), None)

    def trigger_ids(self) -> List[str]:
        return [t.id for t in self.triggers]

    def action_ids(self) -> List[str]:
        return [a.id for a in self.actions]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":          self.id,
            "name":        self.name,
            "version":     self.version,
            "description": self.description,
            "author":      self.author,
            "homepage":    self.homepage,
            "docs_url":    self.docs_url,
            "categories":  self.categories,
            "tags":        self.tags,
            "icon":        self.icon,
            "icon_bg":     self.icon_bg,
            "color":       self.color,
            "auth":        self.auth.to_dict() if self.auth else None,
            "triggers":    [t.to_dict() for t in self.triggers],
            "actions":     [a.to_dict() for a in self.actions],
            "config":      [c.to_dict() for c in self.config],
            "permissions": [p.to_dict() for p in self.permissions],
            "beta":        self.beta,
            "deprecated":  self.deprecated,
            "deprecated_reason": self.deprecated_reason,
            "dependencies":      self.dependencies,
        }
