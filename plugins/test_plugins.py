"""Phase 6 plugin system full validation script."""
import sys
from plugins.sdk.registry import PluginRegistry
from plugins.sdk.validators import PluginValidator
from plugins.sdk.context import PluginContext

registry = PluginRegistry()
registry.load_all()

print("--- Manifest Validation ---")
all_ok = True
for plugin in registry:
    errors = PluginValidator.validate_manifest(plugin.manifest)
    status = "PASS" if not errors else "FAIL"
    print(f"[{status}] {plugin.manifest.id} ({plugin.manifest.name})")
    for e in errors:
        print(f"     -> {e}")
        all_ok = False

print()
print("--- Dry-Run Action Tests ---")
test_cases = [
    ("currency",  "get_rate",            {"from_currency": "USD", "to_currency": "EUR"}),
    ("currency",  "convert",             {"amount": 100, "from_currency": "USD", "to_currency": "EUR"}),
    ("currency",  "get_rate_trend",      {"from_currency": "USD", "to_currency": "EUR", "start_date": "2026-01-01"}),
    ("currency",  "get_currencies",      {}),
    ("weather",   "get_current_weather", {"city": "London"}),
    ("weather",   "get_forecast",        {"city": "Paris", "days": 3}),
    ("weather",   "get_air_quality",     {"city": "Tokyo"}),
    ("weather",   "get_uv_index",        {"city": "Sydney"}),
    ("openai",    "chat_completion",     {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}]}),
    ("openai",    "generate_image",      {"prompt": "A blue mountain at sunset"}),
    ("openai",    "create_embedding",    {"input": "Hello world"}),
    ("openai",    "moderate_text",       {"input": "This is a test."}),
    ("slack",     "send_message",        {"channel": "#general", "text": "Hello!"}),
    ("slack",     "upload_file",         {"channel": "#general", "filename": "test.txt", "content": "Hello"}),
    ("slack",     "create_channel",      {"name": "test-channel"}),
    ("github",    "create_issue",        {"owner": "myorg", "repo": "myrepo", "title": "Test issue"}),
    ("github",    "get_file",            {"owner": "myorg", "repo": "myrepo", "path": "README.md"}),
    ("github",    "trigger_workflow",    {"owner": "myorg", "repo": "myrepo", "workflow_id": "ci.yml", "ref": "main"}),
    ("google",    "append_row",          {"spreadsheet_id": "1BxiMV", "sheet_name": "Sheet1", "values": ["Alice", "alice@test.com"]}),
    ("google",    "read_sheet",          {"spreadsheet_id": "1BxiMV"}),
    ("google",    "send_gmail",          {"to": "alice@test.com", "subject": "Test", "body": "Hello"}),
    ("rest_api",  "get",                 {"url": "https://api.example.com/users"}),
    ("rest_api",  "post",                {"url": "https://api.example.com/data", "body": {"key": "value"}}),
    ("rest_api",  "graphql",             {"url": "https://api.example.com/graphql", "query": "{ users { id } }"}),
    ("email",     "send_email",          {"to": "alice@test.com", "subject": "Test", "body": "Hello World"}),
]

passed = failed = 0
for plugin_id, action_id, params in test_cases:
    plugin = registry.get(plugin_id)
    ctx = PluginContext(plugin_id=plugin_id, run_id="test", node_id=action_id, dry_run=True)
    try:
        result = plugin.execute_action(action_id, ctx, params)
        if result.success:
            print(f"  [PASS] {plugin_id}.{action_id}")
            passed += 1
        else:
            print(f"  [FAIL] {plugin_id}.{action_id}: {result.error}")
            failed += 1
            all_ok = False
    except Exception as e:
        print(f"  [ERR ] {plugin_id}.{action_id}: {type(e).__name__}: {e}")
        failed += 1
        all_ok = False

print()
print("--- Connection Tests (dry-run) ---")
for plugin in registry:
    ctx    = PluginContext(plugin_id=plugin.manifest.id, run_id="test", node_id="test", dry_run=True)
    result = plugin.on_test(ctx)
    status = "PASS" if result.success else "FAIL"
    msg    = result.data.get("message") if result.success else result.error
    print(f"  [{status}] {plugin.manifest.id}: {msg}")

print()
print(f"Action tests: {passed} passed, {failed} failed.")
print("All checks passed!" if all_ok else "Some checks FAILED.")
sys.exit(0 if all_ok else 1)
