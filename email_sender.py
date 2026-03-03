"""Send result.txt to a student via SMTP with attachment."""

from __future__ import annotations

import argparse
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send assignment result email with result.txt attachment")
    parser.add_argument("recipient_email", help="Student email address")
    parser.add_argument("--student-name", default="Student", help="Student name for email body")
    parser.add_argument("--result-file", default="result.txt", help="Path to result text file")
    parser.add_argument("--subject", default="Assignment Evaluation Result", help="Email subject")
    return parser.parse_args()


def load_smtp_config() -> tuple[str, int, str, str]:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port_raw = os.getenv("SMTP_PORT", "587")
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    missing = [
        name
        for name, value in {
            "SMTP_HOST": smtp_host,
            "SENDER_EMAIL": sender_email,
            "SENDER_PASSWORD": sender_password,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required environment variable(s): {', '.join(missing)}")

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError as exc:
        raise ValueError("SMTP_PORT must be an integer") from exc

    return smtp_host, smtp_port, sender_email, sender_password


def build_message(
    sender_email: str,
    recipient_email: str,
    subject: str,
    student_name: str,
    result_file: Path,
) -> EmailMessage:
    if not result_file.exists() or not result_file.is_file():
        raise FileNotFoundError(f"Result file not found: {result_file}")

    attachment_content = result_file.read_bytes()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = recipient_email
    message.set_content(
        f"Hello {student_name},\n\n"
        "Please find attached your assignment evaluation report.\n\n"
        "Regards,\n"
        "Automated Evaluation System"
    )

    message.add_attachment(
        attachment_content,
        maintype="text",
        subtype="plain",
        filename=result_file.name,
    )
    return message


def send_email(message: EmailMessage, smtp_host: str, smtp_port: int, sender_email: str, sender_password: str) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls(context=context)
        server.login(sender_email, sender_password)
        server.send_message(message)


def main() -> int:
    args = parse_args()
    result_path = Path(args.result_file).resolve()

    try:
        smtp_host, smtp_port, sender_email, sender_password = load_smtp_config()
        email_message = build_message(
            sender_email=sender_email,
            recipient_email=args.recipient_email,
            subject=args.subject,
            student_name=args.student_name,
            result_file=result_path,
        )
        send_email(email_message, smtp_host, smtp_port, sender_email, sender_password)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Configuration/File Error: {exc}")
        return 1
    except smtplib.SMTPException as exc:
        print(f"SMTP Error: {exc}")
        return 1
    except OSError as exc:
        print(f"Network/System Error: {exc}")
        return 1

    print(f"Email sent successfully to {args.recipient_email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
