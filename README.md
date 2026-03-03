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
