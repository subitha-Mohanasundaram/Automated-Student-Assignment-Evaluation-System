"""
Plugin CLI
==========
Command-line interface for managing and testing plugins.

Usage:
    python -m plugins list
    python -m plugins info google
    python -m plugins test google --dry-run
    python -m plugins run google send_gmail --params to=alice@example.com subject="Hi" body="Hello" --dry-run
    python -m plugins validate google
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from plugins.sdk.registry import PluginRegistry
from plugins.sdk.context import PluginContext


def _make_context(plugin_id: str, action_id: str = "cli", dry_run: bool = True) -> PluginContext:
    return PluginContext(
        plugin_id = plugin_id,
        run_id    = "cli_run",
        node_id   = action_id,
        config    = {},
        dry_run   = dry_run,
    )


def cmd_list(args: argparse.Namespace, registry: PluginRegistry) -> int:
    plugins = registry.list()
    print(f"\n{'ID':<20} {'NAME':<25} {'VERSION':<10} {'TRIGGERS':<10} {'ACTIONS':<8} STATUS")
    print("-" * 82)
    for p in plugins:
        print(
            f"{p['id']:<20} {p['name']:<25} {p['version']:<10} "
            f"{len(p['triggers']):<10} {len(p['actions']):<8} {p['status']}"
        )
    print(f"\nTotal: {len(plugins)} plugin(s)\n")
    return 0


def cmd_info(args: argparse.Namespace, registry: PluginRegistry) -> int:
    plugin = registry.get(args.plugin_id)
    m      = plugin.manifest
    print(f"\n{'='*60}")
    print(f"  {m.icon or '🔌'}  {m.name}  v{m.version}")
    print(f"{'='*60}")
    print(f"  ID         : {m.id}")
    print(f"  Author     : {m.author}")
    print(f"  Description: {m.description}")
    print(f"  Categories : {', '.join(m.categories)}")
    print(f"  Tags       : {', '.join(m.tags)}")
    print(f"  Auth       : {m.auth.type.value if m.auth else 'none'}")
    print(f"  Beta       : {m.beta}")
    print()
    if m.triggers:
        print(f"  Triggers ({len(m.triggers)}):")
        for t in m.triggers:
            print(f"    [{t.icon or '🔔'}] {t.id:<25} {t.name}")
    if m.actions:
        print(f"\n  Actions ({len(m.actions)}):")
        for a in m.actions:
            ro = " [readonly]" if a.readonly else ""
            print(f"    [{a.icon or '⚡'}] {a.id:<25} {a.name}{ro}")
    if m.config:
        print(f"\n  Config Fields ({len(m.config)}):")
        for c in m.config:
            req = " *" if c.required else ""
            print(f"    {c.name:<25} {c.label}{req}")
    if m.permissions:
        print(f"\n  Permissions ({len(m.permissions)}):")
        for p in m.permissions:
            print(f"    [{p.scope.value}] {p.resource}: {p.description}")
    print()
    return 0


def cmd_validate(args: argparse.Namespace, registry: PluginRegistry) -> int:
    plugin = registry.get(args.plugin_id)
    from plugins.sdk.validators import PluginValidator
    errors = PluginValidator.validate_manifest(plugin.manifest)
    if errors:
        print(f"❌ Validation FAILED for '{args.plugin_id}':")
        for e in errors:
            print(f"   - {e}")
        return 1
    print(f"✅ Plugin '{args.plugin_id}' manifest is valid.")
    return 0


def cmd_test(args: argparse.Namespace, registry: PluginRegistry) -> int:
    plugin  = registry.get(args.plugin_id)
    dry_run = not args.live
    ctx     = _make_context(args.plugin_id, "test", dry_run)
    print(f"\n🔌 Testing plugin '{args.plugin_id}'  (dry_run={dry_run})...")
    result  = plugin.on_test(ctx)
    if result.success:
        print(f"✅ Test PASSED")
        print(f"   Data: {json.dumps(result.data, indent=2)}")
    else:
        print(f"❌ Test FAILED: {result.error}")
    return 0 if result.success else 1


def cmd_run(args: argparse.Namespace, registry: PluginRegistry) -> int:
    plugin    = registry.get(args.plugin_id)
    action_id = args.action_id
    dry_run   = not args.live

    # Parse --param key=value pairs
    params: Dict[str, Any] = {}
    for item in (args.param or []):
        k, _, v = item.partition("=")
        # Try to parse as JSON first
        try:
            params[k.strip()] = json.loads(v.strip())
        except Exception:
            params[k.strip()] = v.strip()

    if args.params_file:
        with open(args.params_file) as f:
            params.update(json.load(f))

    ctx = _make_context(args.plugin_id, action_id, dry_run)
    print(f"\n⚡ Running {args.plugin_id}.{action_id}  (dry_run={dry_run})")
    print(f"   Params: {json.dumps(params, indent=2)}")

    result = plugin.execute_action(action_id, ctx, params)

    if result.success:
        print(f"\n✅ Action SUCCEEDED")
        print(json.dumps(result.data, indent=2, default=str))
    else:
        print(f"\n❌ Action FAILED: {result.error}")
    return 0 if result.success else 1


def main() -> None:
    registry = PluginRegistry()
    registry.load_all()

    parser = argparse.ArgumentParser(
        description="Plugin System CLI — Phase 6",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m plugins list
  python -m plugins info google
  python -m plugins test openai --dry-run
  python -m plugins run weather get_current_weather --param city=London --dry-run
  python -m plugins run currency convert --param amount=100 --param from_currency=USD --param to_currency=EUR --dry-run
        """,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # list
    sub.add_parser("list", help="List all loaded plugins")

    # info
    p_info = sub.add_parser("info", help="Show plugin details")
    p_info.add_argument("plugin_id", help="Plugin ID (e.g. google, slack)")

    # validate
    p_val = sub.add_parser("validate", help="Validate plugin manifest")
    p_val.add_argument("plugin_id", help="Plugin ID")

    # test
    p_test = sub.add_parser("test", help="Run plugin connection test")
    p_test.add_argument("plugin_id", help="Plugin ID")
    p_test.add_argument("--live", action="store_true", help="Run in live mode (makes real API calls)")

    # run
    p_run = sub.add_parser("run", help="Execute a plugin action")
    p_run.add_argument("plugin_id",  help="Plugin ID")
    p_run.add_argument("action_id",  help="Action ID")
    p_run.add_argument("--param",    "-p", action="append", metavar="KEY=VALUE", help="Action parameter")
    p_run.add_argument("--params-file", metavar="FILE", dest="params_file", help="JSON file with params")
    p_run.add_argument("--live",     action="store_true", help="Run in live mode (makes real API calls)")

    args = parser.parse_args()

    import logging
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    handlers = {
        "list":     cmd_list,
        "info":     cmd_info,
        "validate": cmd_validate,
        "test":     cmd_test,
        "run":      cmd_run,
    }

    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler(args, registry))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
