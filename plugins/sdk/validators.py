"""
Plugin Validator
================
Validates plugin manifests at install time and action/trigger
input payloads at runtime.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from plugins.sdk.enums import FieldType
from plugins.sdk.manifest import ConfigField, PluginManifest


class PluginValidator:
    """Validates manifests and runtime inputs against field schemas."""

    # ------------------------------------------------------------------
    # Manifest validation (called at install time)
    # ------------------------------------------------------------------

    @classmethod
    def validate_manifest(cls, manifest: PluginManifest) -> List[str]:
        """Returns list of error strings. Empty list = valid."""
        errors: List[str] = []

        # Identity
        if not manifest.id or not re.match(r'^[a-z][a-z0-9_]*$', manifest.id):
            errors.append("manifest.id must be lowercase snake_case (e.g. 'google_sheets')")
        if not manifest.name:
            errors.append("manifest.name is required")
        if not manifest.version or not re.match(r'^\d+\.\d+\.\d+$', manifest.version):
            errors.append("manifest.version must be SemVer (e.g. '1.0.0')")
        if not manifest.description:
            errors.append("manifest.description is required")
        if not manifest.author:
            errors.append("manifest.author is required")

        # Unique IDs
        tids = [t.id for t in manifest.triggers]
        if len(tids) != len(set(tids)):
            errors.append("Trigger IDs must be unique within the plugin")

        aids = [a.id for a in manifest.actions]
        if len(aids) != len(set(aids)):
            errors.append("Action IDs must be unique within the plugin")

        cfids = [c.name for c in manifest.config]
        if len(cfids) != len(set(cfids)):
            errors.append("Config field names must be unique")

        # At least one capability
        if not manifest.triggers and not manifest.actions:
            errors.append("Plugin must declare at least one trigger or action")

        return errors

    # ------------------------------------------------------------------
    # Config validation (called during install / configure)
    # ------------------------------------------------------------------

    @classmethod
    def validate_config(
        cls,
        fields: List[ConfigField],
        values: Dict[str, Any],
    ) -> List[str]:
        """Validate user-supplied config values against ConfigField definitions."""
        errors: List[str] = []
        for f in fields:
            val = values.get(f.name)
            if val is None or val == "":
                if f.required and f.default is None:
                    errors.append(f"'{f.label}' ({f.name}) is required")
                continue
            errors.extend(cls._validate_field_value(f, val))
        return errors

    @classmethod
    def _validate_field_value(cls, f: ConfigField, val: Any) -> List[str]:
        errs: List[str] = []
        ft = f.type

        if ft == FieldType.EMAIL:
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', str(val)):
                errs.append(f"'{f.name}' must be a valid email address")

        elif ft == FieldType.URL:
            if not str(val).startswith(("http://", "https://")):
                errs.append(f"'{f.name}' must be a valid URL starting with http:// or https://")

        elif ft == FieldType.NUMBER:
            try:
                float(val)
            except (TypeError, ValueError):
                errs.append(f"'{f.name}' must be a number")

        elif ft == FieldType.BOOLEAN:
            if not isinstance(val, bool):
                errs.append(f"'{f.name}' must be true or false")

        elif ft in (FieldType.STRING, FieldType.PASSWORD, FieldType.TEXTAREA):
            s = str(val)
            if f.min_length and len(s) < f.min_length:
                errs.append(f"'{f.name}' must be at least {f.min_length} characters")
            if f.max_length and len(s) > f.max_length:
                errs.append(f"'{f.name}' must be at most {f.max_length} characters")
            if f.pattern and not re.match(f.pattern, s):
                errs.append(f"'{f.name}' does not match required format")

        elif ft == FieldType.SELECT:
            if f.options and val not in f.options:
                errs.append(f"'{f.name}' must be one of: {', '.join(f.options)}")

        elif ft == FieldType.MULTI:
            if isinstance(val, list) and f.options:
                bad = [v for v in val if v not in f.options]
                if bad:
                    errs.append(f"'{f.name}' contains invalid options: {bad}")

        return errs

    # ------------------------------------------------------------------
    # Action input validation (called at runtime)
    # ------------------------------------------------------------------

    @classmethod
    def validate_action_input(
        cls,
        manifest:  PluginManifest,
        action_id: str,
        params:    Dict[str, Any],
    ) -> List[str]:
        action_spec = manifest.get_action(action_id)
        if action_spec is None:
            return [f"Unknown action: '{action_id}' in plugin '{manifest.id}'"]
        errors: List[str] = []
        for f in action_spec.input_fields:
            if f.required and (params.get(f.name) is None or params.get(f.name) == ""):
                errors.append(f"Action '{action_id}': required input '{f.name}' is missing")
        return errors
