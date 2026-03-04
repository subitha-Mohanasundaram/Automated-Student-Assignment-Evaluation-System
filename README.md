# Automated Student Assignment Evaluation System

A Python project scaffold for evaluating student assignment submissions using predefined pytest test cases.

## Project Structure

```text
.
|-- evaluator.py                  # Core grading script
|-- utils.py                      # Helper functions
|-- email_sender.py               # Email report sender
|-- report_generator.py           # Optional report utility
|-- tests/
|   |-- conftest.py               # Loads student submission from --student-file
|   |-- test_student_submission.py# Predefined grading test cases
|   `-- test_evaluator.py         # Unit test for evaluator internals
|-- results/                      # Generated reports
|-- requirements.txt
`-- README.md
```

## Setup

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

## Evaluate a Student File

```bash
python evaluator.py path\\to\\student_solution.py --student-name "Alice"
```

Optional:

```bash
python evaluator.py path\\to\\student_solution.py --result-file results\\result.txt
```

## Output (`result.txt`)

- Student Name
- Total Test Cases
- Passed Cases
- Score

## Run Project Tests

```bash
python -m pytest -q
```

## Auto Evaluate + Email on GitHub Push

This project now supports an automated flow:

1. Student pushes a file under `submissions/<github-username>/...py`
2. GitHub Actions evaluates the pushed file
3. A second workflow sends `result.txt` to the student's email

### Required files

- `students.csv`: maps GitHub username to student name and email
- `.github/workflows/evaluate.yml`: evaluates submission and uploads artifact
- `.github/workflows/send_result_email.yml`: downloads artifact and emails result
- `Dockerfile.grader`: sandbox runtime image for safe evaluation

### Configure student mapping

Update `students.csv`:

```csv
github_username,student_name,email
subitha-Mohanasundaram,Subitha,student@example.com
alice123,Alice,alice@example.com
```

### Configure GitHub Secrets

In GitHub repo: `Settings -> Secrets and variables -> Actions -> New repository secret`

- `SMTP_HOST` (example: `smtp.gmail.com`)
- `SMTP_PORT` (example: `587`)
- `SENDER_EMAIL` (sender mailbox)
- `SENDER_PASSWORD` (app password for sender mailbox)

### Submission path format

Students can push Python or Java files in:

```text
submissions/<github-username>/student_solution.py
submissions/<github-username>/student_solution.java
submissions/<github-username>/<problem-id>/student_solution.py
submissions/<github-username>/<problem-id>/student_solution.java
```

Java submission contract (current version):

- Must define a public class with a static method:
  `addNumbers(double a, double b)`
- Evaluator compiles with `javac` and runs visible + hidden Java test cases.

Problem configuration:

- `problems/<problem-id>/problem.json`
- Controls rubric weights, Python test packs, and Java test cases/contracts.

### Create a New In-House Problem (Scaffold)

Use scaffold utility to create a new problem template quickly:

```bash
python problem_scaffold.py swap_numbers --python-function solve --java-method solve
```

Generated files:

- `problems/swap_numbers/problem.json`
- `tests/problems/swap_numbers/test_visible.py`
- `tests/problems/swap_numbers/test_hidden.py`

Then edit the generated test cases and rubric JSON to match your problem statement.

### How to test end-to-end

1. Add your GitHub username/email in `students.csv`.
2. Commit and push workflow + mapping changes.
3. Push a test student file to `submissions/<your-github-username>/student_solution.py`.
4. Open `Actions` tab:
   - `Evaluate Submission` should pass.
   - `Send Result Email` should pass.
5. Confirm email inbox for mapped student email.

If email workflow fails, open the failed job logs and check:
- student username not found in `students.csv`
- missing SMTP secrets
- invalid SMTP credentials/app password

## Sandbox Execution (Docker)

Evaluation now runs inside Docker in GitHub Actions with:

- no network (`--network none`)
- CPU limit (`--cpus=1.0`)
- memory limit (`--memory=512m`)
- PID limit (`--pids-limit=128`)
- read-only root filesystem (`--read-only`)
- tmpfs scratch space (`--tmpfs /tmp`)
- Linux capability drop (`--cap-drop ALL`)
- no new privileges (`--security-opt no-new-privileges`)

This reduces risk from untrusted student code and is suitable for interview-style coding assessment automation.

## Batch Dashboard Reporting

Use batch reporting to evaluate all student submissions and generate dashboard files:

- `results/batch/batch_report.csv`
- `results/batch/batch_report.json`
- `results/batch/dashboard.md`

Run locally:

```bash
python batch_report.py --submissions-dir submissions --students-file students.csv --output-dir results/batch
```

GitHub workflow:

- `.github/workflows/batch_dashboard.yml`
- Trigger: `workflow_dispatch` or push to `submissions/**.py` / `submissions/**.java` / `students.csv`
- Runs inside Docker sandbox and uploads batch artifacts

## Real-Time Run And Check Commands

Use these commands from Command Prompt to trigger a real-time submission evaluation:

```bat
cd /d C:\Automation
echo # realtime-test>> submissions\subitha-Mohanasundaram\student_solution.py
git add submissions\subitha-Mohanasundaram\student_solution.py
git commit -m "Realtime submission test"
git push
```

After push, check in GitHub:

1. `Actions -> Evaluate Submission` should be green.
2. `Actions -> Send Result Email` should be green.
3. Recipient mailbox should get `Assignment Evaluation Result` with score details and `result.txt`.
