"""
Email Plugin
============
Manifest  : Email sending via SMTP
Auth      : SMTP credentials (username + password)
Triggers  : New Email Received (IMAP polling)
Actions   : Send Email, Send Template Email, Send Email with Attachment,
            Reply to Email, Check Inbox
Icon      : 📧
Version   : 1.0.0
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from plugins.sdk import (
    BasePlugin, PluginManifest, AuthConfig, AuthType,
    TriggerSpec, TriggerType, TriggerOutputField,
    ActionSpec, ActionInputField,
    ConfigField, FieldType,
    Permission, PermissionScope,
    PluginContext, ActionResult, TriggerEvent,
    BasicAuthProvider,
    action, trigger, on_install,
)


class Plugin(BasePlugin):
    """Email plugin — SMTP sending and IMAP reading."""

    manifest = PluginManifest(
        id          = "email",
        name        = "Email (SMTP)",
        version     = "1.0.0",
        description = "Send emails via any SMTP server (Gmail, Outlook, SendGrid, custom). Receive new email triggers via IMAP polling.",
        author      = "Automation Platform Team",
        docs_url    = "https://docs.automation.platform/plugins/email",
        license     = "MIT",
        icon        = "📧",
        icon_bg     = "#EA4335",
        color       = "#EA4335",
        categories  = ["Communication", "Notifications"],
        tags        = ["email", "smtp", "imap", "gmail", "outlook", "sendgrid", "notifications"],

        auth = AuthConfig(
            type        = AuthType.BASIC,
            label       = "SMTP / Email Account",
            help_text   = "Enter your SMTP username (email) and password (or app password).",
            setup_steps = [
                "For Gmail: Enable 2FA → Generate an App Password",
                "For Outlook: Use your email and account password",
                "For SendGrid: Use 'apikey' as username, your API key as password",
                "Set SMTP_USERNAME and SMTP_PASSWORD environment variables",
            ],
        ),

        triggers = [
            TriggerSpec(
                id          = "new_email",
                name        = "New Email Received",
                description = "Fires when a new email arrives in the configured mailbox (IMAP polling).",
                type        = TriggerType.POLLING,
                poll_interval_seconds = 60,
                icon        = "📬",
                output_fields = [
                    TriggerOutputField("message_id",  "string", "Email message ID"),
                    TriggerOutputField("from",        "string", "Sender email address"),
                    TriggerOutputField("from_name",   "string", "Sender display name"),
                    TriggerOutputField("to",          "string", "Recipient address"),
                    TriggerOutputField("subject",     "string", "Email subject"),
                    TriggerOutputField("body_text",   "string", "Plain text body"),
                    TriggerOutputField("body_html",   "string", "HTML body"),
                    TriggerOutputField("received_at", "string", "ISO timestamp"),
                    TriggerOutputField("has_attachments","boolean","True if email has attachments"),
                ],
            ),
        ],

        actions = [
            ActionSpec(
                id          = "send_email",
                name        = "Send Email",
                description = "Send a plain text or HTML email via SMTP.",
                icon        = "📨",
                idempotent  = False,
                input_fields = [
                    ActionInputField("to",          "string",  "Recipient email address(es), comma-separated", required=True),
                    ActionInputField("subject",     "string",  "Email subject",                               required=True),
                    ActionInputField("body",        "string",  "Email body (HTML or plain text)",             required=True),
                    ActionInputField("from_name",   "string",  "Sender display name",                        required=False),
                    ActionInputField("cc",          "string",  "CC recipients (comma-separated)",             required=False),
                    ActionInputField("bcc",         "string",  "BCC recipients (comma-separated)",            required=False),
                    ActionInputField("reply_to",    "string",  "Reply-to address",                           required=False),
                    ActionInputField("is_html",     "boolean", "Send as HTML email",                         required=False, default=True),
                ],
                output_fields = [
                    TriggerOutputField("message_id", "string",  "SMTP message ID"),
                    TriggerOutputField("accepted",   "array",   "Accepted recipient addresses"),
                    TriggerOutputField("rejected",   "array",   "Rejected recipient addresses"),
                ],
            ),
            ActionSpec(
                id          = "send_template_email",
                name        = "Send Template Email",
                description = "Send an email from a named HTML template with variable substitution.",
                icon        = "📝",
                idempotent  = False,
                input_fields = [
                    ActionInputField("to",           "string", "Recipient email",                      required=True),
                    ActionInputField("template_name","string", "Template name (from templates/email/)",required=True),
                    ActionInputField("variables",    "object", "Template variable substitutions",      required=False),
                    ActionInputField("subject",      "string", "Email subject (overrides template)",   required=False),
                ],
                output_fields = [
                    TriggerOutputField("message_id", "string", "SMTP message ID"),
                ],
            ),
            ActionSpec(
                id          = "send_with_attachment",
                name        = "Send Email with Attachment",
                description = "Send an email with one or more file attachments.",
                icon        = "📎",
                idempotent  = False,
                input_fields = [
                    ActionInputField("to",          "string", "Recipient email",       required=True),
                    ActionInputField("subject",     "string", "Email subject",         required=True),
                    ActionInputField("body",        "string", "Email body",            required=True),
                    ActionInputField("attachments", "array",  "List of {name, content_b64, mime_type} objects", required=True),
                ],
                output_fields = [
                    TriggerOutputField("message_id", "string", "SMTP message ID"),
                    TriggerOutputField("attachments_sent", "number", "Number of attachments sent"),
                ],
            ),
            ActionSpec(
                id          = "check_inbox",
                name        = "Check Inbox",
                description = "Check the inbox for unread emails (IMAP).",
                icon        = "📥",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("folder",    "string", "IMAP folder name",          required=False, default="INBOX"),
                    ActionInputField("limit",     "number", "Max emails to return",       required=False, default=10),
                    ActionInputField("unread_only","boolean","Return only unread emails", required=False, default=True),
                ],
                output_fields = [
                    TriggerOutputField("emails",       "array",  "List of email summary objects"),
                    TriggerOutputField("total_unread", "number", "Total unread count"),
                ],
            ),
        ],

        config = [
            ConfigField(
                name        = "smtp_host",
                label       = "SMTP Host",
                type        = FieldType.STRING,
                required    = True,
                placeholder = "smtp.gmail.com",
                help_text   = "SMTP server hostname.",
            ),
            ConfigField(
                name        = "smtp_port",
                label       = "SMTP Port",
                type        = FieldType.NUMBER,
                required    = False,
                default     = 587,
                help_text   = "587 (TLS), 465 (SSL), 25 (unencrypted).",
            ),
            ConfigField(
                name        = "use_tls",
                label       = "Use TLS/STARTTLS",
                type        = FieldType.BOOLEAN,
                required    = False,
                default     = True,
            ),
            ConfigField(
                name        = "from_email",
                label       = "From Email Address",
                type        = FieldType.EMAIL,
                required    = True,
                placeholder = "noreply@yourdomain.com",
            ),
            ConfigField(
                name        = "from_name",
                label       = "From Display Name",
                type        = FieldType.STRING,
                required    = False,
                default     = "Automation Platform",
            ),
            ConfigField(
                name        = "imap_host",
                label       = "IMAP Host (for trigger)",
                type        = FieldType.STRING,
                required    = False,
                placeholder = "imap.gmail.com",
                help_text   = "Required only if using the 'New Email Received' trigger.",
            ),
            ConfigField(
                name        = "imap_port",
                label       = "IMAP Port",
                type        = FieldType.NUMBER,
                required    = False,
                default     = 993,
            ),
        ],

        permissions = [
            Permission(PermissionScope.WRITE, "smtp",    "Send emails via SMTP"),
            Permission(PermissionScope.READ,  "imap",    "Read emails from IMAP mailbox"),
        ],
    )

    def get_auth_provider(self):
        return BasicAuthProvider("SMTP_USERNAME", "SMTP_PASSWORD")

    def _smtp_connect(self, ctx: PluginContext) -> smtplib.SMTP:
        host     = ctx.require_config("smtp_host")
        port     = int(ctx.get_config("smtp_port", 587))
        use_tls  = ctx.get_config("use_tls", True)
        username = ctx.require_secret("SMTP_USERNAME")
        password = ctx.require_secret("SMTP_PASSWORD")

        if port == 465:
            context = ssl.create_default_context()
            server  = smtplib.SMTP_SSL(host, port, context=context)
        else:
            server = smtplib.SMTP(host, port)
            if use_tls:
                server.starttls(context=ssl.create_default_context())

        server.login(username, password)
        return server

    def execute_action(self, action_id: str, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        errors = self.validate_action_params(action_id, params)
        if errors:
            from plugins.sdk.errors import ValidationError
            raise ValidationError(f"Invalid params for '{action_id}'", errors=errors)

        dispatch = {
            "send_email":           self._send_email,
            "send_template_email":  self._send_template_email,
            "send_with_attachment": self._send_with_attachment,
            "check_inbox":          self._check_inbox,
        }
        handler = dispatch.get(action_id)
        if not handler:
            from plugins.sdk.errors import PluginError
            raise PluginError(f"Unknown action: {action_id}")
        return handler(ctx, params)

    @action(id="send_email", name="Send Email", icon="📨")
    def _send_email(self, ctx: PluginContext, params: Dict) -> ActionResult:
        to      = params["to"]
        subject = params["subject"]
        body    = params["body"]
        is_html = params.get("is_html", True)
        ctx.info(f"Sending email to {to}: {subject}")

        if ctx.dry_run:
            return ActionResult.ok(data={"message_id": "<simulated@platform>", "accepted": [to], "rejected": []})

        from_email = ctx.require_config("from_email")
        from_name  = params.get("from_name") or ctx.get_config("from_name", "Automation Platform")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{from_name} <{from_email}>"
        msg["To"]      = to
        if params.get("cc"):       msg["Cc"]       = params["cc"]
        if params.get("reply_to"): msg["Reply-To"] = params["reply_to"]

        content_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, content_type))

        try:
            with self._smtp_connect(ctx) as server:
                recipients = [r.strip() for r in to.split(",")]
                if params.get("cc"):
                    recipients += [r.strip() for r in params["cc"].split(",")]
                if params.get("bcc"):
                    recipients += [r.strip() for r in params["bcc"].split(",")]
                result = server.sendmail(from_email, recipients, msg.as_string())
            rejected = list(result.keys())
            accepted = [r for r in recipients if r not in rejected]
            return ActionResult.ok(data={"message_id": msg["Message-ID"] or "", "accepted": accepted, "rejected": rejected})
        except smtplib.SMTPException as exc:
            return ActionResult.fail(str(exc))

    @action(id="send_template_email", name="Send Template Email", icon="📝")
    def _send_template_email(self, ctx: PluginContext, params: Dict) -> ActionResult:
        import os
        template_name = params["template_name"]
        variables     = params.get("variables", {})
        ctx.info(f"Sending template email '{template_name}' to {params['to']}")

        # Load template from templates/email/ directory
        template_path = f"templates/email/{template_name}.html"
        if ctx.dry_run or not os.path.exists(template_path):
            body = f"<p>Template: {template_name}</p><pre>{variables}</pre>"
        else:
            with open(template_path) as f:
                body = f.read()
            for key, val in variables.items():
                body = body.replace(f"{{{{{key}}}}}", str(val))

        return self._send_email(ctx, {
            "to":      params["to"],
            "subject": params.get("subject", f"Message from {template_name}"),
            "body":    body,
            "is_html": True,
        })

    @action(id="send_with_attachment", name="Send with Attachment", icon="📎")
    def _send_with_attachment(self, ctx: PluginContext, params: Dict) -> ActionResult:
        import base64
        from email.mime.base import MIMEBase
        from email import encoders

        to          = params["to"]
        subject     = params["subject"]
        body        = params["body"]
        attachments = params.get("attachments", [])
        ctx.info(f"Sending email with {len(attachments)} attachment(s) to {to}")

        if ctx.dry_run:
            return ActionResult.ok(data={"message_id": "<simulated@platform>", "attachments_sent": len(attachments)})

        from_email = ctx.require_config("from_email")
        from_name  = ctx.get_config("from_name", "Automation Platform")

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"]    = f"{from_name} <{from_email}>"
        msg["To"]      = to
        msg.attach(MIMEText(body, "html"))

        for att in attachments:
            mime_type = att.get("mime_type", "application/octet-stream")
            main_type, sub_type = mime_type.split("/", 1)
            part = MIMEBase(main_type, sub_type)
            part.set_payload(base64.b64decode(att["content_b64"]))
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=att["name"])
            msg.attach(part)

        try:
            with self._smtp_connect(ctx) as server:
                server.sendmail(from_email, [to], msg.as_string())
            return ActionResult.ok(data={"message_id": "", "attachments_sent": len(attachments)})
        except smtplib.SMTPException as exc:
            return ActionResult.fail(str(exc))

    @action(id="check_inbox", name="Check Inbox", icon="📥", idempotent=True)
    def _check_inbox(self, ctx: PluginContext, params: Dict) -> ActionResult:
        ctx.info("Checking inbox via IMAP...")
        if ctx.dry_run:
            return ActionResult.ok(data={"emails": [{"from": "test@example.com", "subject": "Test", "received_at": "2026-08-05T10:00:00Z"}], "total_unread": 1})

        imap_host = ctx.get_config("imap_host")
        if not imap_host:
            return ActionResult.fail("IMAP host not configured")

        import imaplib, email as email_lib
        imap_port = int(ctx.get_config("imap_port", 993))
        username  = ctx.require_secret("SMTP_USERNAME")
        password  = ctx.require_secret("SMTP_PASSWORD")
        folder    = params.get("folder", "INBOX")
        limit     = int(params.get("limit", 10))

        try:
            mail = imaplib.IMAP4_SSL(imap_host, imap_port)
            mail.login(username, password)
            mail.select(folder)
            status, msgs = mail.search(None, "UNSEEN" if params.get("unread_only", True) else "ALL")
            msg_ids = msgs[0].split()[-limit:]
            emails = []
            for mid in msg_ids:
                _, raw = mail.fetch(mid, "(RFC822)")
                msg = email_lib.message_from_bytes(raw[0][1])
                emails.append({
                    "message_id": msg.get("Message-ID", ""),
                    "from":       msg.get("From", ""),
                    "subject":    msg.get("Subject", ""),
                    "received_at":msg.get("Date", ""),
                })
            mail.close()
            mail.logout()
            return ActionResult.ok(data={"emails": emails, "total_unread": len(msg_ids)})
        except Exception as exc:
            return ActionResult.fail(str(exc))

    def on_test(self, ctx: PluginContext) -> ActionResult:
        if ctx.dry_run:
            return ActionResult.ok(data={"message": "Email plugin SMTP test passed (dry-run)"})
        try:
            with self._smtp_connect(ctx) as server:
                return ActionResult.ok(data={"message": f"Connected to SMTP: {ctx.get_config('smtp_host')}"})
        except Exception as exc:
            return ActionResult.fail(str(exc))
