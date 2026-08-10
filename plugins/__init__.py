"""
Phase 6 — Plugin System
========================
A complete, installable plugin architecture for the Workflow Execution Engine.

Quick start:
    from plugins import PluginRegistry
    registry = PluginRegistry()
    registry.load_all()
    plugin = registry.get('google_sheets')
"""

from plugins.sdk.registry import PluginRegistry
from plugins.sdk.base import BasePlugin
from plugins.sdk.manifest import PluginManifest

__all__ = ["PluginRegistry", "BasePlugin", "PluginManifest"]
__version__ = "1.0.0"
