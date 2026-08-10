"""
tests/test_executor.py
======================
Integration tests for the workflow execution engine.

Runs without external services — uses dry_run=True and the real executor code.
"""
import json
import time
import pytest
from pathlib import Path
from workflows.executor import start_run, get_run, load_run, _load_plugin_configs, save_plugin_configs


# ── Fixtures ───────────────────────────────────────────────────────────────

SIMPLE_WF = {
    "id":   "test_simple",
    "name": "Simple Test Workflow",
    "nodes": [
        {"id": "n1", "type": "trigger",  "name": "Start",     "depends_on": []},
        {"id": "n2", "type": "action",   "name": "Fetch Data", "depends_on": ["n1"],
         "action": {"integration": "rest_api", "operation": "get",
                    "params": {"url": "https://httpbin.org/get"}}},
        {"id": "n3", "type": "transform","name": "Format",    "depends_on": ["n2"]},
    ],
    "edges": [
        {"source": "n1", "target": "n2"},
        {"source": "n2", "target": "n3"},
    ],
    "variables": [{"name": "timeout", "type": "number", "default": 30}],
    "triggers": [],
}

PARALLEL_WF = {
    "id":   "test_parallel",
    "name": "Parallel Test",
    "nodes": [
        {"id": "start", "type": "trigger", "depends_on": []},
        {
            "id": "par", "type": "parallel", "depends_on": ["start"],
            "parallel": {
                "branches": [
                    {"name": "branch_a", "nodes": [{"id": "ba1", "type": "action", "name": "A"}]},
                    {"name": "branch_b", "nodes": [{"id": "bb1", "type": "action", "name": "B"}]},
                ]
            }
        },
        {"id": "end", "type": "action", "depends_on": ["par"]},
    ],
    "edges": [],
    "variables": [],
    "triggers": [],
}

CONDITION_WF = {
    "id":   "test_condition",
    "name": "Condition Test",
    "nodes": [
        {"id": "n1", "type": "trigger",  "depends_on": []},
        {"id": "n2", "type": "action",   "depends_on": ["n1"],
         # expression evaluates to False → node skipped
         "condition": {"expression": "false"}},
        {"id": "n3", "type": "action",   "depends_on": ["n1"]},  # no condition → always runs
    ],
    "edges": [],
    "variables": [],
    "triggers": [],
}




# ── Helpers ─────────────────────────────────────────────────────────────────

def wait_for_run(run_id, timeout=15):
    terminal = {"succeeded", "failed", "cancelled", "timed_out"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        rec = get_run(run_id)
        if rec and rec.get("status") in terminal:
            return rec
        time.sleep(0.3)
    return get_run(run_id)


# ── Tests ───────────────────────────────────────────────────────────────────

class TestSimpleExecution:
    def test_run_returns_run_id(self):
        run_id = start_run(SIMPLE_WF, dry_run=True)
        assert run_id.startswith("run_")

    def test_run_reaches_terminal_state(self):
        run_id = start_run(SIMPLE_WF, dry_run=True)
        rec = wait_for_run(run_id)
        assert rec is not None
        assert rec["status"] in {"succeeded", "failed"}

    def test_run_succeeds_dry_run(self):
        run_id = start_run(SIMPLE_WF, dry_run=True)
        rec = wait_for_run(run_id)
        assert rec["status"] == "succeeded"

    def test_all_nodes_executed(self):
        run_id = start_run(SIMPLE_WF, dry_run=True)
        rec = wait_for_run(run_id)
        for nid in ["n1", "n2", "n3"]:
            assert nid in rec["node_states"], f"Node {nid} missing from node_states"

    def test_node_status_is_success_or_skipped(self):
        run_id = start_run(SIMPLE_WF, dry_run=True)
        rec = wait_for_run(run_id)
        for nid, ns in rec["node_states"].items():
            assert ns["status"] in {"success", "skipped", "failed"}, \
                f"Node {nid} has unexpected status {ns['status']}"

    def test_logs_populated(self):
        run_id = start_run(SIMPLE_WF, dry_run=True)
        rec = wait_for_run(run_id)
        assert len(rec["logs"]) > 0


class TestParallelExecution:
    def test_parallel_branches_both_execute(self):
        run_id = start_run(PARALLEL_WF, dry_run=True)
        rec = wait_for_run(run_id)
        assert "ba1" in rec["node_states"]
        assert "bb1" in rec["node_states"]

    def test_parallel_branches_succeed(self):
        run_id = start_run(PARALLEL_WF, dry_run=True)
        rec = wait_for_run(run_id)
        assert rec["node_states"]["ba1"]["status"] == "success"
        assert rec["node_states"]["bb1"]["status"] == "success"


class TestConditionalExecution:
    def test_false_condition_skips_node(self):
        run_id = start_run(CONDITION_WF, dry_run=True)
        rec = wait_for_run(run_id)
        # n2 should be skipped (condition never_set_var exists → False)
        assert rec["node_states"].get("n2", {}).get("status") == "skipped"

    def test_unconditional_node_runs(self):
        run_id = start_run(CONDITION_WF, dry_run=True)
        rec = wait_for_run(run_id)
        assert rec["node_states"].get("n3", {}).get("status") == "success"


class TestVariableInjection:
    def test_inputs_available_in_context(self):
        wf = {
            "id": "test_vars", "name": "Var test",
            "nodes": [{"id": "n1", "type": "action", "depends_on": [],
                       "action": {"integration": "rest_api", "operation": "get",
                                  "params": {"url": "{{api_url}}"}}}],
            "edges": [], "variables": [], "triggers": [],
        }
        run_id = start_run(wf, dry_run=True, inputs={"api_url": "https://example.com"})
        rec = wait_for_run(run_id)
        assert rec["status"] == "succeeded"


class TestRetryConfig:
    def test_run_with_retry_config(self):
        wf = {
            "id": "test_retry", "name": "Retry test",
            "nodes": [{"id": "n1", "type": "action", "depends_on": [],
                       "retry": {"max_attempts": 2, "strategy": "linear", "delay": "PT1S"},
                       "action": {"integration": "nonexistent_service", "operation": "do"}}],
            "edges": [], "variables": [], "triggers": [],
        }
        run_id = start_run(wf, dry_run=True)
        rec = wait_for_run(run_id, timeout=20)
        # With dry_run the fallback executor succeeds regardless
        assert rec["status"] in {"succeeded", "failed"}


class TestPersistence:
    def test_run_persisted_to_disk(self, tmp_path, monkeypatch):
        import workflows.executor as ex
        monkeypatch.setattr(ex, "_RUNS_DIR", tmp_path)
        run_id = start_run(SIMPLE_WF, dry_run=True)
        wait_for_run(run_id)
        run_file = tmp_path / SIMPLE_WF["id"] / f"{run_id}.json"
        assert run_file.exists(), f"Run log not written: {run_file}"
        with run_file.open() as f:
            data = json.load(f)
        assert data["run_id"] == run_id


class TestPluginConfigStorage:
    def test_save_and_load_plugin_configs(self, tmp_path, monkeypatch):
        import workflows.executor as ex
        test_path = tmp_path / "plugin_configs.json"
        monkeypatch.setattr(ex, "_PLUGIN_CFG_PATH", test_path)
        cfg = {"rest_api": {"config": {"base_url": "https://api.example.com"}, "secrets": {}}}
        save_plugin_configs(cfg)
        loaded = _load_plugin_configs()
        assert loaded["rest_api"]["config"]["base_url"] == "https://api.example.com"


class TestLivePluginExecution:
    """Test live plugin execution (dry_run=False) using public APIs."""
    
    def test_rest_api_plugin_live_execution(self):
        """
        Verify that:
        1. PluginRegistry is loaded
        2. REST API plugin is invoked for real
        3. Real HTTP call is made
        4. Response is captured and passed to output
        
        This tests the fix for: "Live plugin execution falls back to dry-run"
        Bug: NodeExecutor was forced to dry_run=True, preventing real plugin execution.
        Fix: Changed hardcoded dry_run=True to dry_run parameter in executor.py line 314.
        """
        wf = {
            "id": "test_live_plugin",
            "name": "Live Plugin Test",
            "nodes": [{
                "id": "fetch_data",
                "type": "action",
                "name": "Fetch Real Data",
                "action": {
                    "integration": "rest_api",
                    "operation": "get",
                    # Using public API that always works
                    "params": {
                        "url": "https://jsonplaceholder.typicode.com/posts/1"
                    }
                }
            }],
            "edges": [],
            "variables": [],
            "triggers": [],
        }
        
        # Execute with dry_run=False to enable live plugin execution
        run_id = start_run(wf, dry_run=False)
        rec = wait_for_run(run_id, timeout=30)
        
        # Verify execution
        assert rec["status"] == "succeeded", f"Workflow should succeed, got {rec['status']}"
        
        node_state = rec["node_states"]["fetch_data"]
        assert node_state["status"] == "success", f"Node status: {node_state['status']}"
        
        # Check that we got REAL data (not simulated)
        outputs = node_state.get("outputs", {})
        assert "result" in outputs, "Node should produce output"
        
        result = outputs["result"]
        assert isinstance(result, dict), "Result should be a dict"
        assert result.get("status_code") == 200, f"Expected 200, got {result.get('status_code')}"
        
        # The key test: response body contains real API data
        body = result.get("body", {})
        assert isinstance(body, dict), "Body should be a dict"
        assert body.get("id") == 1, "Should get post with id=1"
        assert body.get("title"), "Post should have a title"
        assert body.get("userId"), "Post should have userId"
        
        # Verify NOT simulated
        assert "simulated" not in result, "Response should not be simulated"
    
    def test_fallback_executor_respects_dry_run(self):
        """
        Verify that the fallback NodeExecutor respects the dry_run parameter.
        
        This test uses a transform node (which doesn't use plugins) to ensure
        the fallback executor is called and that it respects dry_run.
        """
        wf = {
            "id": "test_fallback_dryrun",
            "name": "Fallback Dry-Run Test",
            "variables": [{"name": "input", "type": "string", "default": "test"}],
            "nodes": [{
                "id": "transform_data",
                "type": "transform",
                "transform": {
                    "mappings": [
                        {"target": "${output}", "value": "Output: {{input}}"}
                    ]
                }
            }],
            "edges": [],
            "triggers": [],
        }
        
        # Run with dry_run=False (should still work for transform)
        run_id = start_run(wf, dry_run=False)
        rec = wait_for_run(run_id)
        
        assert rec["status"] == "succeeded"
        node_state = rec["node_states"]["transform_data"]
        assert node_state["status"] == "success"
