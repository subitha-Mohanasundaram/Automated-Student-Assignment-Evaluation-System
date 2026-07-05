# Architecture

## High-Level Flow

```text
User (Student/Instructor/Admin)
  |
  v
Auth (JWT HttpOnly Cookie) + RBAC
  |
  v
Student Submission
  |
  v
Dashboard (FastAPI)  <---- Instructor/Student Views
  |
  v
OpenAI Multi-Agent (GPT-5)  [optional]
  |
  v
Remote MCP Tool Server (SSE)
  |
  v
Execution Sandbox (Docker optional)
  |
  v
Results + Reports (results/*.json)
```

## Components

- Dashboard/UI: `web_app.py`
- Remote MCP server: `mcp_remote_server.py` (wrapper) -> `platform_mcp/mcp_remote_server.py`
- Tools:
  - Execution: `platform_mcp/tools_execution.py`
  - Tests/Scoring: `platform_mcp/tools_tests.py`
  - Hidden test expansion: `platform_mcp/tools_test_expansion.py`
  - Plagiarism: `platform_mcp/tools_plagiarism.py`
  - Analysis: `platform_mcp/tools_analysis.py`
  - Feedback: `platform_mcp/tools_feedback.py`
  - Problem pack generation: `platform_mcp/tools_problem_gen.py`
- Multi-agent (local, JSON messages): `agents/*`, `evaluation/multi_agent_runner.py`
- OpenAI MCP runner: `run_openai_agent.py`, `assignment_intel/openai_mcp_agent.py`

## Auth + RBAC

- DB table: `users` in `results/platform.db`
- Endpoints:
  - `GET /login`, `GET /register`
  - `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`
- Session: JWT stored in an HttpOnly `session` cookie.
- Protected routes:
  - `/instructor/*` requires role `instructor` or `admin`
  - `/admin/*` requires role `admin`

## Job Queue + Worker

Heavy operations run asynchronously so the web server stays responsive.

- DB table: `jobs` (`problem_generation`, `solution_evaluation`)
- Worker: `worker.py`
- Instructor creates assignment:
  1. assignment saved
  2. `problem_generation` job enqueued
  3. worker generates metadata/tests/reference solution with retries and marks assignment `active=1` on success
- Student submits solution:
  1. submission stored
  2. evaluation row created
  3. `solution_evaluation` job enqueued
  4. worker runs Docker sandbox evaluation and saves report

## AI Generation Pipeline Reliability

Implemented in `assignment_intel/problem_generation_pipeline.py`:

- Retries up to 3 times (config: `AI_GEN_RETRIES`)
- Validations:
  - reference solution not empty
  - at least 3 visible tests
  - hidden + stress tests exist
  - expected output counts match inputs
- Failures logged to `logs/ai_generation_errors.jsonl`

## Observability

Worker writes append-only JSONL logs:

- `logs/agent_trace.json` (job errors/traces)
- `logs/tool_calls.json` (job payloads)
- `logs/evaluation_metrics.json` (evaluation outcomes)
