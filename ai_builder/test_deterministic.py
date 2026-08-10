"""Phase 7 deterministic tests — no API calls required."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ai_builder.estimator import CostEstimator
from ai_builder.detector import MistakeDetector
from ai_builder.architect import ArchitectureGenerator
from ai_builder.editor import NLEditor
from ai_builder.models import WorkflowIssue

# ---- Minimal test workflow ----------------------------------------
TEST_WF = {
    "schema_version": "1.0",
    "workflow_id":    "test_wf",
    "name":           "Test Workflow",
    "version":        "1.0.0",
    "description":    "Test workflow for Phase 7 validation",
    "metadata":       {"owner": "test@example.com", "created_at": "2026-08-05T00:00:00Z", "updated_at": "2026-08-05T00:00:00Z"},
    "settings":       {"execution_mode": "dag", "max_concurrent_runs": 5, "timeout": "PT10M"},
    "variables":      [{"name": "email", "type": "string", "default": "", "description": "Recipient email", "scope": "workflow"}],
    "triggers":       [{"id": "cron_trigger", "type": "cron", "cron": {"expression": "0 9 * * *", "timezone": "UTC"}}],
    "nodes": [
        {
            "id":          "fetch_weather",
            "name":        "Fetch Weather Data",
            "type":        "action",
            "description": "Get current weather",
            "depends_on":  [],
            "action":      {"integration": "openweathermap", "operation": "get_current_weather", "params": {"city": "London"}},
            "retry":       {"max_attempts": 3, "backoff_strategy": "exponential"},
            "timeout":     {"duration": "PT30S"},
        },
        {
            "id":          "process_data",
            "name":        "Process Weather Data",
            "type":        "transform",
            "description": "Transform weather data",
            "depends_on":  ["fetch_weather"],
            "transform":   {"mappings": [{"target": "temp_celsius", "value": "{{fetch_weather.temperature}}"}]},
        },
        {
            "id":          "ai_summary",
            "name":        "Generate Summary",
            "type":        "ai",
            "description": "AI-generated weather summary",
            "depends_on":  ["process_data"],
            "ai":          {"provider": "openai", "model": "gpt-4o-mini", "prompt": "Summarize the weather: {{process_data.temp_celsius}}°C", "output_var": "summary"},
        },
        {
            "id":          "check_severe",
            "name":        "Check for Severe Weather",
            "type":        "condition",
            "description": "Branch on severe conditions",
            "depends_on":  ["ai_summary"],
            "condition_node": {"expression": "{{fetch_weather.weather_code}} >= 95", "branches": [{"condition": "true", "next": "send_alert"}, {"condition": "false", "next": "send_daily_email"}]},
        },
        {
            "id":          "send_alert",
            "name":        "Send Severe Weather Alert",
            "type":        "notification",
            "description": "Send urgent Slack + email alert",
            "depends_on":  ["check_severe"],
            "notification":{"targets": [{"channel": "slack", "to": "#weather-alerts"}, {"channel": "smtp", "to": "{{email}}"}]},
        },
        {
            "id":          "send_daily_email",
            "name":        "Send Daily Weather Email",
            "type":        "notification",
            "description": "Send regular daily digest",
            "depends_on":  ["check_severe"],
            "notification":{"targets": [{"channel": "smtp", "to": "{{email}}", "subject": "Daily Weather: {{ai_summary.summary}}"}]},
        },
    ],
}

# ---- Broken workflow for mistake detection -------------------------
BROKEN_WF = {
    "schema_version": "1.0",
    "workflow_id":    "broken_wf",
    "name":           "Broken Workflow",
    "version":        "1.0.0",
    "description":    "A workflow with intentional issues",
    "triggers":       [{"id": "manual", "type": "manual"}],
    "nodes": [
        {
            "id":         "node_a",
            "name":       "Node A",
            "type":       "action",
            "depends_on": ["nonexistent_node"],   # INVALID_DEPENDENCY
            "action":     {"integration": "rest_api", "operation": "get"},
            # Missing retry, missing timeout
        },
        {
            "id":         "node_a",              # DUPLICATE_NODE_ID
            "name":       "Node A Duplicate",
            "type":       "action",
            "depends_on": [],
        },
        {
            "id":         "loop_node",
            "name":       "Unbounded Loop",
            "type":       "loop",
            "depends_on": [],
            "loop":       {"mode": "while", "collection": "items"},  # No max_iterations
        },
    ],
}

passed = failed = 0

def check(name, cond, msg=""):
    global passed, failed
    if cond:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}: {msg}")
        failed += 1


print("=" * 60)
print("  Phase 7 — Deterministic Tests (no API calls)")
print("=" * 60)

# ---------------------------------------------------------------
print("\n--- CostEstimator ---")
est = CostEstimator(runs_per_day=100)
result = est.estimate(TEST_WF)

check("estimate returns EstimateResult", result.success)
check("node estimates count", len(result.node_estimates) == len(TEST_WF["nodes"]),
      f"got {len(result.node_estimates)}")
check("cost_per_run >= 0", result.cost_per_run_usd >= 0)
check("ai_cost > 0", result.ai_cost_usd > 0, f"ai_cost={result.ai_cost_usd}")
check("cost_per_month = cost_per_day * 30", abs(result.cost_per_month_usd - result.cost_per_day_usd * 30) < 0.001)
check("runtime_ms > 0", result.estimated_runtime_ms > 0)
check("critical_path_ms > 0", result.critical_path_ms > 0)
check("runs_per_day stored", result.runs_per_day == 100)

print(f"\n  Cost per run : ${result.cost_per_run_usd:.5f}")
print(f"  Cost/month   : ${result.cost_per_month_usd:.2f}")
print(f"  Runtime      : {result.estimated_runtime_ms}ms  critical: {result.critical_path_ms}ms")
for ne in result.node_estimates:
    print(f"    {ne.node_id:<25} ${ne.cost_usd_per_run:.5f}  {ne.runtime_ms}ms")

# ---------------------------------------------------------------
print("\n--- MistakeDetector (rule-based only) ---")

class MockAIClient:
    """Stub AI client that returns empty AI issues — no API calls."""
    session_cost_usd = 0.0
    session_tokens   = {"input": 0, "output": 0}
    def chat_json(self, *a, **kw):
        return {"issues": []}
    def chat(self, *a, **kw):
        return ""

mock_client = MockAIClient()
detector    = MistakeDetector(mock_client)

# Test healthy workflow
good_result = detector.detect(TEST_WF)
check("healthy wf: no errors", good_result.error_count == 0, f"got {good_result.error_count} errors")
check("healthy wf: health_score > 70", good_result.health_score > 70, f"score={good_result.health_score}")
print(f"\n  Healthy workflow: score={good_result.health_score:.0f}  issues={len(good_result.issues)}")
for issue in good_result.issues:
    print(f"    [{issue.severity}] {issue.code}: {issue.message[:60]}")

# Test broken workflow
bad_result = detector.detect(BROKEN_WF)
codes = {i.code for i in bad_result.issues}
check("broken wf: DUPLICATE_NODE_ID detected",   "DUPLICATE_NODE_ID"   in codes, f"codes={codes}")
check("broken wf: INVALID_DEPENDENCY detected",  "INVALID_DEPENDENCY"  in codes, f"codes={codes}")
check("broken wf: UNBOUNDED_LOOP detected",      "UNBOUNDED_LOOP"      in codes, f"codes={codes}")
check("broken wf: health_score < 100", bad_result.health_score < 100, f"score={bad_result.health_score}")
print(f"\n  Broken workflow: score={bad_result.health_score:.0f}  errors={bad_result.error_count}  warnings={bad_result.warning_count}")

# ---------------------------------------------------------------
print("\n--- ArchitectureGenerator ---")
arch_gen = ArchitectureGenerator(mock_client)
arch     = arch_gen.generate(TEST_WF)

check("arch success", arch.success)
check("mermaid generated", "flowchart" in arch.mermaid.lower() or "graph" in arch.mermaid.lower() or "classDef" in arch.mermaid)
check("ascii_art generated", len(arch.ascii_art) > 100)
check("components = node count", len(arch.components) == len(TEST_WF["nodes"]),
      f"got {len(arch.components)} components")
check("data_flows > 0", len(arch.data_flows) > 0)

print(f"\n  Components : {len(arch.components)}")
print(f"  Data flows : {len(arch.data_flows)}")
print(f"  Mermaid len: {len(arch.mermaid)} chars")
try:
    print(f"\n{arch.ascii_art[:400]}...")
except UnicodeEncodeError:
    print("\n  [ASCII art skipped — terminal encoding limitation]")

# ---------------------------------------------------------------
print("\n--- NLEditor (deterministic commands) ---")
editor = NLEditor(mock_client)

# Test add_retry
edit1 = editor.edit(TEST_WF, "Add retry to fetch_weather node")
# The deterministic handler looks for parsed command from AI (mocked),
# so this will fall back to AI apply. With mock client it'll fail gracefully.
# Let's test the deterministic apply directly.
from ai_builder.editor import NLEditor
ed = NLEditor(mock_client)

# Test _apply_add_retry directly
import copy
wf_copy = copy.deepcopy(TEST_WF)
# Remove retry from fetch_weather for the test
wf_copy["nodes"][0].pop("retry", None)
updated, changes = ed._apply_add_retry(wf_copy, {"node_id": "fetch_weather", "max_attempts": 5})
check("add_retry: success", updated is not None)
check("add_retry: changes recorded", len(changes) > 0)
check("add_retry: retry on node", updated["nodes"][0].get("retry", {}).get("max_attempts") == 5)

# Test _apply_set_timeout
updated2, changes2 = ed._apply_set_timeout(wf_copy, {"node_id": "fetch_weather", "duration_seconds": 120})
check("set_timeout: success", updated2 is not None)
check("set_timeout: PT120S", updated2["nodes"][0].get("timeout", {}).get("duration") == "PT120S")

# Test _apply_rename
updated3, changes3 = ed._apply_rename(wf_copy, {"node_id": "fetch_weather", "new_name": "Get Weather"})
check("rename: success", updated3 is not None)
check("rename: new name set", updated3["nodes"][0].get("name") == "Get Weather")

# Test _apply_add_delay
updated4, changes4 = ed._apply_add_delay(wf_copy, {"after_node_id": "fetch_weather", "duration_seconds": 30})
check("add_delay: success", updated4 is not None)
check("add_delay: delay node inserted", any(n.get("type") == "delay" for n in updated4.get("nodes", [])))

# Test _apply_remove_node
updated5, changes5 = ed._apply_remove_node(wf_copy, {"node_id": "ai_summary"})
check("remove_node: success", updated5 is not None)
check("remove_node: node gone", not any(n.get("id") == "ai_summary" for n in updated5.get("nodes", [])))

# ---------------------------------------------------------------
print("\n--- Mermaid Output Sample ---")
print(arch.mermaid[:600])

# ---------------------------------------------------------------
print(f"\n{'='*60}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*60}")
sys.exit(0 if failed == 0 else 1)
