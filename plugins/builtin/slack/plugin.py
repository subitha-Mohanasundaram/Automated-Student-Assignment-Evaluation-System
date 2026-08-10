"""
Slack Plugin
============
Manifest  : Slack messaging and event integration
Auth      : Bearer token (Bot Token)
Triggers  : New Message in Channel, New Mention, App Mention, New Reaction
Actions   : Send Message, Send DM, Update Message, Delete Message,
            Upload File, Add Reaction, Create Channel, Invite User
Icon      : 💬
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
    BearerTokenProvider,
    action, trigger, on_install,
    NetworkError, AuthError,
)


class Plugin(BasePlugin):
    """Slack plugin — messaging, channels, and events."""

    manifest = PluginManifest(
        id          = "slack",
        name        = "Slack",
        version     = "1.0.0",
        description = "Send messages, upload files, manage channels, and react to Slack events in real time.",
        author      = "Automation Platform Team",
        homepage    = "https://slack.com",
        docs_url    = "https://docs.automation.platform/plugins/slack",
        license     = "MIT",
        icon        = "💬",
        icon_bg     = "#4A154B",
        color       = "#4A154B",
        categories  = ["Communication", "Team Collaboration"],
        tags        = ["slack", "messaging", "notifications", "channels", "team"],

        auth = AuthConfig(
            type            = AuthType.BEARER,
            label           = "Connect Slack Workspace",
            api_key_env     = "SLACK_BOT_TOKEN",
            help_url        = "https://api.slack.com/start/building",
            help_text       = "Create a Slack App and copy the Bot Token (xoxb-).",
            setup_steps     = [
                "Go to https://api.slack.com/apps → Create New App",
                "Add OAuth scopes: chat:write, channels:read, files:write, reactions:write",
                "Install the app to your workspace",
                "Copy the Bot User OAuth Token (xoxb-...)",
                "Set SLACK_BOT_TOKEN environment variable",
            ],
        ),

        triggers = [
            TriggerSpec(
                id          = "new_message",
                name        = "New Channel Message",
                description = "Fires when a new message is posted in a channel the bot is a member of.",
                type        = TriggerType.WEBHOOK,
                webhook_path= "/webhooks/slack/events",
                icon        = "💬",
                output_fields = [
                    TriggerOutputField("channel",    "string", "Channel ID"),
                    TriggerOutputField("channel_name","string","Channel name"),
                    TriggerOutputField("user",       "string", "Slack user ID"),
                    TriggerOutputField("username",   "string", "Slack username"),
                    TriggerOutputField("text",       "string", "Message text"),
                    TriggerOutputField("ts",         "string", "Message timestamp"),
                    TriggerOutputField("thread_ts",  "string", "Thread timestamp if reply"),
                ],
            ),
            TriggerSpec(
                id          = "app_mention",
                name        = "App Mention",
                description = "Fires when someone @-mentions your bot.",
                type        = TriggerType.WEBHOOK,
                webhook_path= "/webhooks/slack/events",
                icon        = "🔔",
                output_fields = [
                    TriggerOutputField("channel",  "string", "Channel ID"),
                    TriggerOutputField("user",     "string", "User who mentioned the bot"),
                    TriggerOutputField("text",     "string", "Full message text"),
                    TriggerOutputField("ts",       "string", "Message timestamp"),
                ],
            ),
            TriggerSpec(
                id          = "new_reaction",
                name        = "New Reaction Added",
                description = "Fires when a user adds a reaction emoji to a message.",
                type        = TriggerType.WEBHOOK,
                webhook_path= "/webhooks/slack/events",
                icon        = "😄",
                output_fields = [
                    TriggerOutputField("reaction",    "string", "Emoji name (without colons)"),
                    TriggerOutputField("user",        "string", "User who added the reaction"),
                    TriggerOutputField("item_channel","string", "Channel of the reacted message"),
                    TriggerOutputField("item_ts",     "string", "Timestamp of the reacted message"),
                ],
            ),
        ],

        actions = [
            ActionSpec(
                id          = "send_message",
                name        = "Send Message",
                description = "Post a message to a Slack channel or DM.",
                icon        = "📤",
                idempotent  = False,
                input_fields = [
                    ActionInputField("channel", "string", "Channel name or ID (e.g. #general or C1234)", required=True),
                    ActionInputField("text",    "string", "Message text (supports mrkdwn)",              required=True),
                    ActionInputField("thread_ts","string","Reply to thread timestamp",                   required=False),
                    ActionInputField("username", "string","Override bot display name",                   required=False),
                    ActionInputField("icon_emoji","string","Override bot icon (e.g. :robot_face:)",      required=False),
                ],
                output_fields = [
                    TriggerOutputField("ts",       "string", "Message timestamp"),
                    TriggerOutputField("channel",  "string", "Channel the message was posted to"),
                    TriggerOutputField("message_url","string","Permalink to the message"),
                ],
            ),
            ActionSpec(
                id          = "send_dm",
                name        = "Send Direct Message",
                description = "Send a private DM to a Slack user.",
                icon        = "✉️",
                idempotent  = False,
                input_fields = [
                    ActionInputField("user_id", "string", "Slack user ID (U-prefixed)", required=True),
                    ActionInputField("text",    "string", "Message text",               required=True),
                ],
                output_fields = [
                    TriggerOutputField("ts",      "string", "Message timestamp"),
                    TriggerOutputField("channel", "string", "DM channel ID"),
                ],
            ),
            ActionSpec(
                id          = "update_message",
                name        = "Update Message",
                description = "Edit an existing Slack message.",
                icon        = "✏️",
                idempotent  = True,
                input_fields = [
                    ActionInputField("channel", "string", "Channel ID",         required=True),
                    ActionInputField("ts",      "string", "Message timestamp",  required=True),
                    ActionInputField("text",    "string", "New message text",   required=True),
                ],
                output_fields = [
                    TriggerOutputField("ts",    "string", "Updated message timestamp"),
                ],
            ),
            ActionSpec(
                id          = "upload_file",
                name        = "Upload File",
                description = "Upload a file to a Slack channel.",
                icon        = "📎",
                idempotent  = False,
                input_fields = [
                    ActionInputField("channel",   "string", "Channel ID or name", required=True),
                    ActionInputField("filename",  "string", "File name",          required=True),
                    ActionInputField("content",   "string", "File content",       required=True),
                    ActionInputField("filetype",  "string", "File type (e.g. txt, json)", required=False, default="txt"),
                    ActionInputField("title",     "string", "File title",         required=False),
                ],
                output_fields = [
                    TriggerOutputField("file_id",  "string", "Slack file ID"),
                    TriggerOutputField("file_url", "string", "File permalink"),
                ],
            ),
            ActionSpec(
                id          = "add_reaction",
                name        = "Add Reaction",
                description = "Add an emoji reaction to a message.",
                icon        = "👍",
                idempotent  = True,
                input_fields = [
                    ActionInputField("channel",  "string", "Channel ID",          required=True),
                    ActionInputField("ts",       "string", "Message timestamp",   required=True),
                    ActionInputField("reaction", "string", "Emoji name (no colons)", required=True),
                ],
                output_fields = [],
            ),
            ActionSpec(
                id          = "create_channel",
                name        = "Create Channel",
                description = "Create a new Slack channel.",
                icon        = "➕",
                idempotent  = False,
                input_fields = [
                    ActionInputField("name",      "string", "Channel name (lowercase, no spaces)", required=True),
                    ActionInputField("is_private", "boolean","Make channel private",               required=False, default=False),
                ],
                output_fields = [
                    TriggerOutputField("channel_id",   "string", "New channel ID"),
                    TriggerOutputField("channel_name", "string", "New channel name"),
                ],
            ),
        ],

        config = [
            ConfigField(
                name        = "default_channel",
                label       = "Default Channel",
                type        = FieldType.STRING,
                required    = False,
                placeholder = "#general",
                help_text   = "Default channel for notifications when no channel is specified.",
            ),
            ConfigField(
                name        = "bot_name",
                label       = "Bot Display Name",
                type        = FieldType.STRING,
                required    = False,
                default     = "Automation Bot",
            ),
            ConfigField(
                name        = "bot_icon",
                label       = "Bot Icon Emoji",
                type        = FieldType.STRING,
                required    = False,
                default     = ":robot_face:",
            ),
        ],

        permissions = [
            Permission(PermissionScope.WRITE,        "messages",  "Post messages to channels"),
            Permission(PermissionScope.READ,         "channels",  "List and read channel info"),
            Permission(PermissionScope.WRITE,        "files",     "Upload files to channels"),
            Permission(PermissionScope.WRITE,        "reactions", "Add emoji reactions"),
            Permission(PermissionScope.NOTIFICATION, "events",    "Receive Slack event webhooks"),
        ],

        lifecycle = [
            LifecycleHook(LifecycleEvent.INSTALL,   "on_install", "Verify bot token and permissions"),
        ],
    )

    def get_auth_provider(self):
        return BearerTokenProvider("SLACK_BOT_TOKEN")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @on_install
    def on_install(self, ctx: PluginContext) -> None:
        ctx.info("Slack plugin installed. Testing bot token...")
        result = self.on_test(ctx)
        if not result.success:
            ctx.warning(f"Slack token test failed: {result.error}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def execute_action(self, action_id: str, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        errors = self.validate_action_params(action_id, params)
        if errors:
            from plugins.sdk.errors import ValidationError
            raise ValidationError(f"Invalid params for '{action_id}'", errors=errors)

        dispatch = {
            "send_message":  self._send_message,
            "send_dm":       self._send_dm,
            "update_message":self._update_message,
            "upload_file":   self._upload_file,
            "add_reaction":  self._add_reaction,
            "create_channel":self._create_channel,
        }
        handler = dispatch.get(action_id)
        if not handler:
            from plugins.sdk.errors import PluginError
            raise PluginError(f"Unknown action: {action_id}")
        return handler(ctx, params)

    @action(id="send_message", name="Send Message", icon="📤")
    def _send_message(self, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        channel = params["channel"]
        text    = params["text"]
        ctx.info(f"Sending Slack message to {channel}: {text[:60]}...")

        if ctx.dry_run:
            return ActionResult.ok(data={"ts": "1234567890.000000", "channel": channel, "message_url": f"https://slack.com/archives/{channel}/p1234567890000000"})

        token   = ctx.require_secret("SLACK_BOT_TOKEN")
        payload = {"channel": channel, "text": text}
        if params.get("thread_ts"):
            payload["thread_ts"] = params["thread_ts"]
        if params.get("username"):
            payload["username"] = params["username"]
        result  = ctx.http_post(
            "https://slack.com/api/chat.postMessage",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        if not result.get("ok"):
            return ActionResult.fail(result.get("error", "Unknown Slack error"))
        return ActionResult.ok(data={
            "ts":          result.get("ts"),
            "channel":     result.get("channel"),
            "message_url": f"https://slack.com/archives/{result.get('channel')}/p{result.get('ts', '').replace('.', '')}",
        })

    @action(id="send_dm", name="Send Direct Message", icon="✉️")
    def _send_dm(self, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        user_id = params["user_id"]
        text    = params["text"]
        ctx.info(f"Sending Slack DM to {user_id}")

        if ctx.dry_run:
            return ActionResult.ok(data={"ts": "1234567890.000000", "channel": f"D{user_id}"})

        token = ctx.require_secret("SLACK_BOT_TOKEN")
        # Open DM channel first
        open_result = ctx.http_post(
            "https://slack.com/api/conversations.open",
            json={"users": user_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        channel_id = open_result.get("channel", {}).get("id")
        return self._send_message(ctx, {"channel": channel_id, "text": text})

    @action(id="update_message", name="Update Message", icon="✏️")
    def _update_message(self, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        ctx.info(f"Updating message {params['ts']} in {params['channel']}")
        if ctx.dry_run:
            return ActionResult.ok(data={"ts": params["ts"]})
        token = ctx.require_secret("SLACK_BOT_TOKEN")
        result = ctx.http_post(
            "https://slack.com/api/chat.update",
            json={"channel": params["channel"], "ts": params["ts"], "text": params["text"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        return ActionResult.ok(data={"ts": result.get("ts")})

    @action(id="upload_file", name="Upload File", icon="📎")
    def _upload_file(self, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        ctx.info(f"Uploading file '{params['filename']}' to Slack {params['channel']}")
        if ctx.dry_run:
            return ActionResult.ok(data={"file_id": "F_simulated", "file_url": "https://files.slack.com/simulated"})
        token = ctx.require_secret("SLACK_BOT_TOKEN")
        result = ctx.http_post(
            "https://slack.com/api/files.upload",
            data={
                "channels": params["channel"],
                "filename": params["filename"],
                "filetype": params.get("filetype", "txt"),
                "content":  params["content"],
                "title":    params.get("title", params["filename"]),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        file_ = result.get("file", {})
        return ActionResult.ok(data={"file_id": file_.get("id"), "file_url": file_.get("permalink")})

    @action(id="add_reaction", name="Add Reaction", icon="👍")
    def _add_reaction(self, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        ctx.info(f"Adding :{params['reaction']}: to message {params['ts']}")
        if ctx.dry_run:
            return ActionResult.ok()
        token = ctx.require_secret("SLACK_BOT_TOKEN")
        ctx.http_post(
            "https://slack.com/api/reactions.add",
            json={"channel": params["channel"], "timestamp": params["ts"], "name": params["reaction"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        return ActionResult.ok()

    @action(id="create_channel", name="Create Channel", icon="➕")
    def _create_channel(self, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        ctx.info(f"Creating Slack channel: {params['name']}")
        if ctx.dry_run:
            return ActionResult.ok(data={"channel_id": "C_simulated", "channel_name": params["name"]})
        token = ctx.require_secret("SLACK_BOT_TOKEN")
        result = ctx.http_post(
            "https://slack.com/api/conversations.create",
            json={"name": params["name"], "is_private": params.get("is_private", False)},
            headers={"Authorization": f"Bearer {token}"},
        )
        channel = result.get("channel", {})
        return ActionResult.ok(data={"channel_id": channel.get("id"), "channel_name": channel.get("name")})

    # ------------------------------------------------------------------
    # Webhook handling
    # ------------------------------------------------------------------

    def handle_webhook(self, trigger_id: str, ctx: PluginContext, payload: Dict[str, Any], headers: Dict[str, str]) -> List[TriggerEvent]:
        event_type = payload.get("event", {}).get("type", "")
        events     = []
        if event_type in ("message", "message.channels") and trigger_id == "new_message":
            event_data = payload["event"]
            events.append(TriggerEvent(
                trigger_id = trigger_id,
                plugin_id  = self.manifest.id,
                payload    = {
                    "channel":  event_data.get("channel"),
                    "user":     event_data.get("user"),
                    "text":     event_data.get("text"),
                    "ts":       event_data.get("ts"),
                },
            ))
        return events

    # ------------------------------------------------------------------
    # Test
    # ------------------------------------------------------------------

    def on_test(self, ctx: PluginContext) -> ActionResult:
        if ctx.dry_run:
            return ActionResult.ok(data={"message": "Slack plugin connection test passed (dry-run)"})
        try:
            token  = ctx.require_secret("SLACK_BOT_TOKEN")
            result = ctx.http_get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {token}"},
            )
            if result.get("ok"):
                return ActionResult.ok(data={"team": result.get("team"), "user": result.get("user"), "message": "Connected to Slack"})
            return ActionResult.fail(result.get("error", "auth.test failed"))
        except Exception as exc:
            return ActionResult.fail(str(exc))
