# Mini-LeetCode  (AI-Powered Assignment Evaluation Platform)

This repository is a production-style, local-first coding assignment platform:

- Instructor creates assignments with **title + description only**
- Background worker uses **AI + MCP tools** to generate:
  - expanded problem statement + constraints + examples
  - **visible + hidden + stress** test packs
  - a reference solution and expected outputs (computed safely in Docker)
- Students submit solutions in a browser editor
- Evaluations run in a sandbox (Docker) and produce JSON reports + a dashboard view

## Quick Start (Recommended)

1. Create `.env`:

```powershell
cd C:\Automation
Copy-Item .env.example .env
notepad .env
```

Set:

- `AI_PROVIDER=openai`
- `OPENAI_MODEL=gpt-5`
- `OPENAI_API_KEY=...`

2. Start services (3 PowerShell windows):

**Window 1 (MCP SSE server):**

```powershell
cd C:\Automation
.\.venv\Scripts\Activate.ps1
python mcp_remote_server.py
```

**Window 2 (Worker):**

```powershell
cd C:\Automation
.\.venv\Scripts\Activate.ps1
python worker.py
```

**Window 3 (Web app):**

```powershell
cd C:\Automation
.\.venv\Scripts\Activate.ps1
python web_app.py
```

Open:

- `http://127.0.0.1:8080/`

## Authentication Modes

### Demo Mode (fastest for college demos)

Student: any username (no password).
Instructor: shared password from env.

```powershell
$env:DEMO_AUTH="1"
$env:INSTRUCTOR_PASSWORD="Teach@123"
python web_app.py
```

### Secure Mode (register + password)

Unset demo mode and use `/register` + `/login`.

```powershell
Remove-Item Env:DEMO_AUTH -ErrorAction SilentlyContinue
python web_app.py
```

## Main URLs

- Landing: `/`
- Assignments list: `/assignments`
- Student dashboard: `/me`
- Instructor panel: `/instructor/assignments`
- Instructor analytics: `/instructor/analytics`
- Report viewer: `/report?path=...`
- Leaderboard: `/leaderboard?assignment_id=<id>`

## Instructor Workflow

1. Go to `/instructor/assignments`
2. Create assignment (title + description)
3. Worker generates problem pack in the background
4. If generation succeeds, publish (or use the **Publish** button if needed)
5. Students can now submit solutions

If generation fails:

- Check `logs/ai_generation_errors.jsonl`
- Ensure `.env` has `AI_PROVIDER=openai` + `OPENAI_API_KEY`
- Ensure Docker Desktop is running
- Click **Retry gen**

## Student Workflow

1. Go to `/assignments`
2. Open a problem
3. Write code and **Submit**
4. Watch progress: `/evaluation?id=<evaluation_id>`
5. View final report in the dashboard (`/me`)
6. Edit/resubmit from `/me` (and optionally delete a submission)

## Project Layout

```text
.
|-- web_app.py                  # FastAPI web UI (mini-leetcode)
|-- worker.py                   # background jobs: generation + evaluation
|-- mcp_remote_server.py        # FastMCP SSE server exposing tools
|-- evaluator.py                # core grading engine (pytest + IO mode)
|-- assignment_intel/           # orchestration, DB, sandbox runner, agents
|-- platform_mcp/               # MCP tool implementations (exec/tests/analysis/gen)
|-- templates/                  # Jinja + Tailwind UI
|-- tests/                      # unit tests for platform internals
|-- docker/ + Dockerfile.grader # sandbox runtime image(s)
|-- results/                    # sqlite DB + generated reports
|-- logs/                       # tool calls + generation errors + metrics
|-- scripts/                    # optional utilities (legacy/ops helpers)
|-- examples/                   # sample submissions + sample outputs
`-- requirements.txt
```

## CLI (Optional)

Run a grading evaluation against a file:

```powershell
python evaluator.py path\to\solution.py --student-name "Alice"
```

Run OpenAI agent (uses MCP tool list):

```powershell
python run_openai_agent.py C:\Automation\examples\student_ok.py --student-name Alice --problem-id add_numbers --language python
```

Run local multi-agent pipeline (no OpenAI required):

```powershell
python run_multi_agent_local.py C:\Automation\examples\two_sum_ok.py --student-name Alice --problem-id two_sum --language python
```

## Optional Utilities (scripts/)

- `scripts/manage_assignments.py` (assignment/testcase management)
- `scripts/batch_report.py` (batch reports)
- `scripts/batch_evaluate.py` (batch evaluation)
- `scripts/mcp_server.py` (legacy MCP stdio JSON-RPC)

