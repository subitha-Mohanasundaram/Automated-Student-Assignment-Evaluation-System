"""
Google Plugin — Google Sheets, Gmail, Drive, Forms
===================================================
Manifest  : Google Workspace integration
Auth      : OAuth2 (service account or user OAuth)
Triggers  : New Spreadsheet Row, New Form Response, New Gmail Message
Actions   : Append Row, Update Cell, Send Email, Create Document,
            Upload File, Read Sheet
Icon      : 🔵
Version   : 1.0.0
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from plugins.sdk import (
    BasePlugin, PluginManifest, AuthConfig, AuthType,
    TriggerSpec, TriggerType, TriggerOutputField,
    ActionSpec, ActionInputField,
    ConfigField, FieldType,
    Permission, PermissionScope,
    LifecycleHook, LifecycleEvent,
    PluginContext, ActionResult, TriggerEvent,
    BearerTokenProvider, ApiKeyProvider,
    action, trigger, on_install, on_configure,
    NetworkError, AuthError, NotFoundError,
)


class Plugin(BasePlugin):
    """Google Workspace plugin — Sheets, Gmail, Drive."""

    manifest = PluginManifest(
        id          = "google",
        name        = "Google",
        version     = "1.0.0",
        description = "Connect to Google Sheets, Gmail, Drive, and Forms. Read and write data, send emails, and react to new form responses.",
        author      = "Automation Platform Team",
        homepage    = "https://workspace.google.com",
        docs_url    = "https://docs.automation.platform/plugins/google",
        support_url = "https://support.automation.platform",
        license     = "MIT",
        icon        = "🔵",
        icon_bg     = "#4285F4",
        color       = "#4285F4",
        categories  = ["Productivity", "Data", "Communication"],
        tags        = ["google", "sheets", "gmail", "drive", "forms", "spreadsheet"],

        # ---- Authentication ------------------------------------------------
        auth = AuthConfig(
            type               = AuthType.OAUTH2,
            label              = "Connect Google Account",
            oauth_authorize_url= "https://accounts.google.com/o/oauth2/v2/auth",
            oauth_token_url    = "https://oauth2.googleapis.com/token",
            oauth_scopes       = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/forms.responses.readonly",
            ],
            api_key_env        = "GOOGLE_SERVICE_ACCOUNT_JSON",
            help_url           = "https://docs.automation.platform/plugins/google/auth",
            help_text          = "Authorize via OAuth2 or supply a service account JSON key.",
            setup_steps        = [
                "Go to Google Cloud Console → Enable Sheets, Gmail, Drive APIs",
                "Create a Service Account and download the JSON key",
                "Set GOOGLE_SERVICE_ACCOUNT_JSON env var to the key path",
            ],
        ),

        # ---- Triggers -------------------------------------------------------
        triggers = [
            TriggerSpec(
                id          = "new_spreadsheet_row",
                name        = "New Spreadsheet Row",
                description = "Fires when a new row is appended to a Google Sheet.",
                type        = TriggerType.POLLING,
                poll_interval_seconds = 60,
                icon        = "📊",
                output_fields = [
                    TriggerOutputField("row_index",     "number", "Row number"),
                    TriggerOutputField("row_values",    "array",  "Cell values in the new row"),
                    TriggerOutputField("spreadsheet_id","string", "Spreadsheet ID"),
                    TriggerOutputField("sheet_name",    "string", "Sheet tab name"),
                ],
                example_payload = {
                    "row_index": 42,
                    "row_values": ["Alice", "alice@example.com", "2026-08-05"],
                    "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
                    "sheet_name": "Responses",
                },
            ),
            TriggerSpec(
                id          = "new_form_response",
                name        = "New Google Form Response",
                description = "Fires when someone submits a Google Form.",
                type        = TriggerType.POLLING,
                poll_interval_seconds = 30,
                icon        = "📝",
                output_fields = [
                    TriggerOutputField("response_id",   "string", "Form response ID"),
                    TriggerOutputField("respondent_email","string","Respondent email"),
                    TriggerOutputField("answers",       "object", "Key-value answers"),
                    TriggerOutputField("submitted_at",  "string", "ISO timestamp"),
                ],
            ),
            TriggerSpec(
                id          = "new_gmail_message",
                name        = "New Gmail Message",
                description = "Fires when a new email arrives matching the filter.",
                type        = TriggerType.POLLING,
                poll_interval_seconds = 120,
                icon        = "📧",
                output_fields = [
                    TriggerOutputField("message_id",    "string", "Gmail message ID"),
                    TriggerOutputField("from",          "string", "Sender email"),
                    TriggerOutputField("subject",       "string", "Email subject"),
                    TriggerOutputField("body",          "string", "Plain-text body"),
                    TriggerOutputField("received_at",   "string", "ISO timestamp"),
                ],
            ),
        ],

        # ---- Actions --------------------------------------------------------
        actions = [
            ActionSpec(
                id          = "append_row",
                name        = "Append Row to Sheet",
                description = "Appends a new row of values to the specified Google Sheet.",
                icon        = "➕",
                idempotent  = False,
                input_fields = [
                    ActionInputField("spreadsheet_id", "string", "Google Spreadsheet ID", required=True),
                    ActionInputField("sheet_name",     "string", "Sheet tab name",        required=True,  default="Sheet1"),
                    ActionInputField("values",         "array",  "Array of cell values",  required=True),
                ],
                output_fields = [
                    TriggerOutputField("updated_range", "string", "A1 notation of updated cells"),
                    TriggerOutputField("row_index",     "number", "Index of appended row"),
                ],
            ),
            ActionSpec(
                id          = "update_cell",
                name        = "Update Cell",
                description = "Update a specific cell or range in a Google Sheet.",
                icon        = "✏️",
                idempotent  = True,
                input_fields = [
                    ActionInputField("spreadsheet_id", "string", "Spreadsheet ID", required=True),
                    ActionInputField("range",          "string", "A1 notation (e.g. Sheet1!B2)", required=True),
                    ActionInputField("value",          "string", "New cell value", required=True),
                ],
                output_fields = [
                    TriggerOutputField("updated_cells", "number", "Number of cells updated"),
                ],
            ),
            ActionSpec(
                id          = "read_sheet",
                name        = "Read Sheet Rows",
                description = "Read all rows from a Google Sheet, optionally filtered.",
                icon        = "📖",
                readonly    = True,
                idempotent  = True,
                input_fields = [
                    ActionInputField("spreadsheet_id", "string", "Spreadsheet ID", required=True),
                    ActionInputField("sheet_name",     "string", "Sheet tab name", required=False, default="Sheet1"),
                    ActionInputField("range",          "string", "Optional A1 range", required=False),
                ],
                output_fields = [
                    TriggerOutputField("rows",         "array",  "Array of row value arrays"),
                    TriggerOutputField("headers",      "array",  "Column headers (first row)"),
                    TriggerOutputField("row_count",    "number", "Total number of data rows"),
                ],
            ),
            ActionSpec(
                id          = "send_gmail",
                name        = "Send Email via Gmail",
                description = "Send an email from the connected Gmail account.",
                icon        = "📨",
                idempotent  = False,
                input_fields = [
                    ActionInputField("to",      "string", "Recipient email address", required=True),
                    ActionInputField("subject", "string", "Email subject",           required=True),
                    ActionInputField("body",    "string", "Email body (HTML or text)",required=True),
                    ActionInputField("cc",      "string", "CC address(es)",          required=False),
                    ActionInputField("bcc",     "string", "BCC address(es)",         required=False),
                ],
                output_fields = [
                    TriggerOutputField("message_id", "string", "Gmail message ID"),
                    TriggerOutputField("thread_id",  "string", "Gmail thread ID"),
                ],
            ),
            ActionSpec(
                id          = "create_document",
                name        = "Create Google Doc",
                description = "Create a new Google Docs document.",
                icon        = "📄",
                idempotent  = False,
                input_fields = [
                    ActionInputField("title",   "string", "Document title",   required=True),
                    ActionInputField("content", "string", "Initial content",  required=False),
                    ActionInputField("folder_id","string","Drive folder ID",  required=False),
                ],
                output_fields = [
                    TriggerOutputField("document_id",  "string", "Google Docs document ID"),
                    TriggerOutputField("document_url", "string", "Web URL of the document"),
                ],
            ),
        ],

        # ---- Config fields --------------------------------------------------
        config = [
            ConfigField(
                name        = "spreadsheet_id",
                label       = "Default Spreadsheet ID",
                type        = FieldType.STRING,
                required    = False,
                placeholder = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
                help_text   = "Default spreadsheet used when no explicit ID is given.",
            ),
            ConfigField(
                name        = "default_sheet",
                label       = "Default Sheet Tab",
                type        = FieldType.STRING,
                required    = False,
                default     = "Sheet1",
            ),
        ],

        # ---- Permissions ----------------------------------------------------
        permissions = [
            Permission(PermissionScope.READ,  "spreadsheets", "Read data from Google Sheets"),
            Permission(PermissionScope.WRITE, "spreadsheets", "Write data to Google Sheets"),
            Permission(PermissionScope.WRITE, "gmail",        "Send emails via Gmail"),
            Permission(PermissionScope.READ,  "forms",        "Read Google Form responses"),
            Permission(PermissionScope.WRITE, "drive",        "Create and upload files in Drive"),
        ],

        # ---- Lifecycle hooks ------------------------------------------------
        lifecycle = [
            LifecycleHook(LifecycleEvent.INSTALL,   "on_install",   "Verify service account permissions"),
            LifecycleHook(LifecycleEvent.CONFIGURE, "on_configure", "Validate default spreadsheet ID"),
        ],

        dependencies = [],
    )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def get_auth_provider(self):
        return BearerTokenProvider("GOOGLE_ACCESS_TOKEN")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @on_install
    def on_install(self, ctx: PluginContext) -> None:
        ctx.info("Google plugin installed. Verifying API access...")
        if not ctx.dry_run:
            try:
                result = ctx.http_get(
                    "https://www.googleapis.com/oauth2/v1/tokeninfo",
                    headers={"Authorization": f"Bearer {ctx.require_secret('GOOGLE_ACCESS_TOKEN')}"},
                )
                ctx.info(f"Token valid for: {result.get('email', 'unknown')}")
            except Exception as exc:
                ctx.warning(f"Could not verify Google token: {exc}")

    @on_configure
    def on_configure(self, ctx: PluginContext, config: Dict[str, Any]) -> None:
        ctx.info(f"Google plugin configured. Default sheet: {config.get('default_sheet', 'Sheet1')}")

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    def execute_action(self, action_id: str, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        errors = self.validate_action_params(action_id, params)
        if errors:
            from plugins.sdk.errors import ValidationError
            raise ValidationError(f"Invalid params for action '{action_id}'", errors=errors)

        dispatch = {
            "append_row":      self._append_row,
            "update_cell":     self._update_cell,
            "read_sheet":      self._read_sheet,
            "send_gmail":      self._send_gmail,
            "create_document": self._create_document,
        }
        handler = dispatch.get(action_id)
        if handler is None:
            from plugins.sdk.errors import PluginError
            raise PluginError(f"Unknown action: {action_id}")
        return handler(ctx, params)

    # ---- Actions ---------------------------------------------------------

    @action(id="append_row", name="Append Row to Sheet", idempotent=False, icon="➕")
    def _append_row(self, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        spreadsheet_id = params["spreadsheet_id"]
        sheet          = params.get("sheet_name", "Sheet1")
        values         = params["values"]
        ctx.info(f"Appending row to {spreadsheet_id}/{sheet}: {values}")

        if ctx.dry_run:
            return ActionResult.ok(data={"updated_range": f"{sheet}!A999", "row_index": 999})

        token = ctx.require_secret("GOOGLE_ACCESS_TOKEN")
        url   = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet}!A1:append"
        body  = {"values": [values], "majorDimension": "ROWS"}
        result = ctx.http_post(
            url,
            json=body,
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            headers={"Authorization": f"Bearer {token}"},
        )
        updates = result.get("updates", {})
        return ActionResult.ok(data={
            "updated_range": updates.get("updatedRange", ""),
            "row_index":     updates.get("updatedRows", 0),
        })

    @action(id="update_cell", name="Update Cell", idempotent=True, icon="✏️")
    def _update_cell(self, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        spreadsheet_id = params["spreadsheet_id"]
        range_         = params["range"]
        value          = params["value"]
        ctx.info(f"Updating cell {range_} = {value!r}")

        if ctx.dry_run:
            return ActionResult.ok(data={"updated_cells": 1})

        token = ctx.require_secret("GOOGLE_ACCESS_TOKEN")
        url   = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_}"
        body  = {"values": [[value]], "majorDimension": "ROWS"}
        result = ctx.http_put(
            url,
            json=body,
            params={"valueInputOption": "USER_ENTERED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        return ActionResult.ok(data={"updated_cells": result.get("updatedCells", 1)})

    @action(id="read_sheet", name="Read Sheet Rows", readonly=True, idempotent=True, icon="📖")
    def _read_sheet(self, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        spreadsheet_id = params["spreadsheet_id"]
        sheet          = params.get("sheet_name", "Sheet1")
        range_         = params.get("range", sheet)
        ctx.info(f"Reading sheet {spreadsheet_id}/{range_}")

        if ctx.dry_run:
            return ActionResult.ok(data={"rows": [["Name", "Email"], ["Alice", "alice@test.com"]], "headers": ["Name", "Email"], "row_count": 1})

        token  = ctx.require_secret("GOOGLE_ACCESS_TOKEN")
        url    = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_}"
        result = ctx.http_get(url, headers={"Authorization": f"Bearer {token}"})
        rows   = result.get("values", [])
        headers = rows[0] if rows else []
        data_rows = rows[1:] if len(rows) > 1 else []
        return ActionResult.ok(data={"rows": data_rows, "headers": headers, "row_count": len(data_rows)})

    @action(id="send_gmail", name="Send Email via Gmail", idempotent=False, icon="📨")
    def _send_gmail(self, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        import base64
        from email.mime.text import MIMEText
        to      = params["to"]
        subject = params["subject"]
        body    = params["body"]
        ctx.info(f"Sending email to {to}: {subject}")

        if ctx.dry_run:
            return ActionResult.ok(data={"message_id": "simulated_msg_id", "thread_id": "simulated_thread"})

        token   = ctx.require_secret("GOOGLE_ACCESS_TOKEN")
        message = MIMEText(body, "html")
        message["to"]      = to
        message["subject"] = subject
        if params.get("cc"):
            message["cc"] = params["cc"]
        raw     = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result  = ctx.http_post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            json={"raw": raw},
            headers={"Authorization": f"Bearer {token}"},
        )
        return ActionResult.ok(data={"message_id": result.get("id"), "thread_id": result.get("threadId")})

    @action(id="create_document", name="Create Google Doc", idempotent=False, icon="📄")
    def _create_document(self, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        title = params["title"]
        ctx.info(f"Creating Google Doc: {title}")

        if ctx.dry_run:
            return ActionResult.ok(data={"document_id": "simulated_doc_id", "document_url": f"https://docs.google.com/document/d/simulated/edit"})

        token  = ctx.require_secret("GOOGLE_ACCESS_TOKEN")
        result = ctx.http_post(
            "https://docs.googleapis.com/v1/documents",
            json={"title": title},
            headers={"Authorization": f"Bearer {token}"},
        )
        doc_id = result.get("documentId")
        return ActionResult.ok(data={
            "document_id":  doc_id,
            "document_url": f"https://docs.google.com/document/d/{doc_id}/edit",
        })

    # ------------------------------------------------------------------
    # Trigger polling
    # ------------------------------------------------------------------

    @trigger(id="new_spreadsheet_row", name="New Spreadsheet Row", icon="📊")
    def poll_trigger(self, trigger_id: str, ctx: PluginContext, since: Any = None) -> List[TriggerEvent]:
        if trigger_id == "new_spreadsheet_row":
            return self._poll_new_rows(ctx, since)
        elif trigger_id == "new_form_response":
            return self._poll_form_responses(ctx, since)
        elif trigger_id == "new_gmail_message":
            return self._poll_gmail(ctx, since)
        return []

    def _poll_new_rows(self, ctx: PluginContext, since: Any) -> List[TriggerEvent]:
        ctx.info("Polling Google Sheets for new rows...")
        if ctx.dry_run:
            return []
        # Real implementation would track last seen row index
        return []

    def _poll_form_responses(self, ctx: PluginContext, since: Any) -> List[TriggerEvent]:
        ctx.info("Polling Google Forms for new responses...")
        if ctx.dry_run:
            return []
        return []

    def _poll_gmail(self, ctx: PluginContext, since: Any) -> List[TriggerEvent]:
        ctx.info("Polling Gmail for new messages...")
        if ctx.dry_run:
            return []
        return []

    # ------------------------------------------------------------------
    # Test connection
    # ------------------------------------------------------------------

    def on_test(self, ctx: PluginContext) -> ActionResult:
        if ctx.dry_run:
            return ActionResult.ok(data={"message": "Google plugin connection test passed (dry-run)"})
        try:
            token = ctx.require_secret("GOOGLE_ACCESS_TOKEN")
            result = ctx.http_get(
                "https://www.googleapis.com/oauth2/v1/tokeninfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            return ActionResult.ok(data={"email": result.get("email"), "message": "Connected successfully"})
        except Exception as exc:
            return ActionResult.fail(str(exc))
