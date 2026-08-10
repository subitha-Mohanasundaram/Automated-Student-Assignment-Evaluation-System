"""
Plugin Registry
===============
Central registry that discovers, loads, validates, and instantiates plugins.

Supports:
  - Built-in plugins (bundled at plugins/builtin/)
  - Installed plugins (dropped into plugins/installed/)
  - Entry-point plugins (installed via pip into 'automation.plugins' group)
  - Manual registration (for testing / dynamic plugins)
"""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Type

from plugins.sdk.enums import PluginStatus
from plugins.sdk.errors import PluginError, ValidationError

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Central registry for all available plugins.
    Instantiated once and shared across the engine.
    """
    _BUILTIN_DIR       = Path(__file__).parent.parent / "builtin"
    _INSTALLED_DIR     = Path(__file__).parent.parent / "installed"
    _ENTRY_POINT_GROUP = "automation.plugins"

    def __init__(self) -> None:
        self._plugins:  Dict[str, "BasePlugin"]  = {}   # type: ignore[name-defined]
        self._statuses: Dict[str, PluginStatus]  = {}

    # ------------------------------------------------------------------
    # Discovery & Loading
    # ------------------------------------------------------------------

    def load_all(
        self,
        *,
        builtin:      bool = True,
        installed:    bool = True,
        entrypoints:  bool = True,
    ) -> None:
        """Discover and load all available plugins."""
        if builtin:
            self._load_from_directory(self._BUILTIN_DIR)
        if installed:
            self._INSTALLED_DIR.mkdir(parents=True, exist_ok=True)
            self._load_from_directory(self._INSTALLED_DIR)
        if entrypoints:
            self._load_from_entrypoints()
        logger.info("PluginRegistry: %d plugin(s) loaded", len(self._plugins))

    def _load_from_directory(self, directory: Path) -> None:
        if not directory.exists():
            return
        for plugin_dir in sorted(directory.iterdir()):
            if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
                continue
            plugin_file = plugin_dir / "plugin.py"
            if not plugin_file.exists():
                continue
            try:
                self._load_plugin_file(plugin_file, plugin_dir.name)
            except Exception as exc:
                logger.error("Failed to load plugin from %s: %s", plugin_dir, exc)

    def _load_plugin_file(self, plugin_file: Path, plugin_id: str) -> None:
        spec = importlib.util.spec_from_file_location(f"_plugin_{plugin_id}", plugin_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec from {plugin_file}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)   # type: ignore[union-attr]

        plugin_cls = getattr(module, "Plugin", None)
        if plugin_cls is None:
            raise ImportError(f"No 'Plugin' class found in {plugin_file}")
        self._register_class(plugin_cls)

    def _load_from_entrypoints(self) -> None:
        try:
            from importlib.metadata import entry_points
            eps = entry_points(group=self._ENTRY_POINT_GROUP)
            for ep in eps:
                try:
                    plugin_cls = ep.load()
                    self._register_class(plugin_cls)
                except Exception as exc:
                    logger.error("Failed to load entry-point plugin '%s': %s", ep.name, exc)
        except Exception:
            pass

    def _register_class(self, plugin_cls: type) -> None:
        from plugins.sdk.base import BasePlugin
        from plugins.sdk.validators import PluginValidator
        if not issubclass(plugin_cls, BasePlugin):
            raise TypeError(f"{plugin_cls.__name__} must subclass BasePlugin")
        instance: BasePlugin = plugin_cls()
        manifest = instance.manifest

        errors = PluginValidator.validate_manifest(manifest)
        if errors:
            raise ValidationError(
                f"Plugin '{manifest.id}' manifest invalid",
                errors=errors,
            )

        self._plugins[manifest.id]  = instance
        self._statuses[manifest.id] = PluginStatus.ACTIVE
        logger.info("  Loaded plugin: %s v%s  [%d trigger(s), %d action(s)]",
                    manifest.name, manifest.version,
                    len(manifest.triggers), len(manifest.actions))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, plugin_cls: type) -> None:
        """Manually register a plugin class (testing / dynamic use)."""
        self._register_class(plugin_cls)

    def get(self, plugin_id: str) -> "BasePlugin":   # type: ignore[name-defined]
        """Return plugin instance by ID."""
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise PluginError(f"Plugin not found: '{plugin_id}'", code="PLUGIN_NOT_FOUND")
        return plugin

    def list(self) -> List[Dict]:
        """Return manifest dicts for all loaded plugins."""
        result = []
        for p in self._plugins.values():
            d = p.manifest.to_dict()
            d["status"] = self._statuses.get(p.manifest.id, PluginStatus.ACTIVE).value
            result.append(d)
        return result

    def ids(self) -> List[str]:
        return list(self._plugins.keys())

    def status(self, plugin_id: str) -> PluginStatus:
        return self._statuses.get(plugin_id, PluginStatus.INACTIVE)

    def enable(self, plugin_id: str) -> None:
        if plugin_id not in self._plugins:
            raise PluginError(f"Plugin not found: {plugin_id}")
        self._statuses[plugin_id] = PluginStatus.ACTIVE
        logger.info("Plugin '%s' enabled.", plugin_id)

    def disable(self, plugin_id: str) -> None:
        if plugin_id not in self._plugins:
            raise PluginError(f"Plugin not found: {plugin_id}")
        self._statuses[plugin_id] = PluginStatus.INACTIVE
        logger.info("Plugin '%s' disabled.", plugin_id)

    def unload(self, plugin_id: str) -> None:
        """Remove a plugin from the registry."""
        self._plugins.pop(plugin_id, None)
        self._statuses.pop(plugin_id, None)
        logger.info("Plugin '%s' unloaded.", plugin_id)

    def __iter__(self) -> Iterator:
        return iter(self._plugins.values())

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, plugin_id: str) -> bool:
        return plugin_id in self._plugins
