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

Students must push Python files in:

```text
submissions/<github-username>/student_solution.py
```

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
