"""
REST API Plugin
===============
Manifest  : Generic configurable HTTP REST API client
Auth      : Configurable (none, API key, Bearer, Basic)
Triggers  : Polling Endpoint, Webhook Receiver
Actions   : GET, POST, PUT, PATCH, DELETE, GraphQL Query
Icon      : 🌐
Version   : 1.0.0
"""
from __future__ import annotations

from typing import Any, Dict, List

from plugins.sdk import (
    BasePlugin, PluginManifest, AuthConfig, AuthType,
    TriggerSpec, TriggerType, TriggerOutputField,
    ActionSpec, ActionInputField,
    ConfigField, FieldType,
    Permission, PermissionScope,
    PluginContext, ActionResult, TriggerEvent,
    NoAuthProvider,
    action, trigger,
)


class Plugin(BasePlugin):
    """Generic REST API plugin — make any HTTP request from a workflow."""

    manifest = PluginManifest(
        id          = "rest_api",
        name        = "REST API",
        version     = "1.0.0",
        description = "Make HTTP requests to any REST or GraphQL API. Supports GET, POST, PUT, PATCH, DELETE with configurable authentication, headers, and body templates.",
        author      = "Automation Platform Team",
        docs_url    = "https://docs.automation.platform/plugins/rest_api",
        license     = "MIT",
        icon        = "🌐",
        icon_bg     = "#6366F1",
        color       = "#6366F1",
        categories  = ["Integration", "Developer Tools", "Generic"],
        tags        = ["http", "rest", "api", "webhook", "graphql", "generic"],

        auth = AuthConfig(
            type        = AuthType.CUSTOM,
            label       = "Configure API Authentication",
            help_text   = "Select the auth method in configuration. API key/token is stored securely.",
        ),

        triggers = [
            TriggerSpec(
                id          = "polling_endpoint",
                name        = "Poll Endpoint",
                description = "Periodically poll a REST endpoint and fire when the response changes.",
                type        = TriggerType.POLLING,
                poll_interval_seconds = 300,
                icon        = "🔄",
                output_fields = [
                    TriggerOutputField("url",          "string", "Polled URL"),
                    TriggerOutputField("status_code",  "number", "HTTP response status"),
                    TriggerOutputField("body",         "object", "Response body (parsed JSON)"),
                    TriggerOutputField("changed_at",   "string", "Timestamp of change"),
                ],
            ),
            TriggerSpec(
                id          = "webhook_receiver",
                name        = "Receive Webhook",
                description = "Receive incoming HTTP webhooks and pass the payload to the workflow.",
                type        = TriggerType.WEBHOOK,
                webhook_path= "/webhooks/rest_api/receive",
                icon        = "📥",
                output_fields = [
                    TriggerOutputField("payload",   "object", "Request body (JSON or form data)"),
                    TriggerOutputField("headers",   "object", "Request headers"),
                    TriggerOutputField("method",    "string", "HTTP method"),
                    TriggerOutputField("query",     "object", "Query string parameters"),
                ],
            ),
        ],

        actions = [
            ActionSpec(
                id          = "get",
                name        = "GET Request",
                description = "Make an HTTP GET request and return the response.",
                icon        = "📥",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("url",            "string", "Request URL",                              required=True),
                    ActionInputField("headers",        "object", "Extra request headers (key: value)",       required=False),
                    ActionInputField("query_params",   "object", "Query string parameters",                  required=False),
                    ActionInputField("timeout_seconds","number", "Request timeout in seconds",               required=False, default=30),
                    ActionInputField("follow_redirects","boolean","Follow HTTP redirects",                   required=False, default=True),
                ],
                output_fields = [
                    TriggerOutputField("status_code",  "number", "HTTP response status code"),
                    TriggerOutputField("body",         "any",    "Response body (JSON or text)"),
                    TriggerOutputField("headers",      "object", "Response headers"),
                    TriggerOutputField("success",      "boolean","True if status < 400"),
                ],
            ),
            ActionSpec(
                id          = "post",
                name        = "POST Request",
                description = "Make an HTTP POST request with a JSON or form body.",
                icon        = "📤",
                idempotent  = False,
                input_fields = [
                    ActionInputField("url",            "string", "Request URL",                           required=True),
                    ActionInputField("body",           "object", "Request body (sent as JSON)",           required=False),
                    ActionInputField("form_data",      "object", "Form data (application/x-www-form-urlencoded)", required=False),
                    ActionInputField("headers",        "object", "Extra request headers",                 required=False),
                    ActionInputField("timeout_seconds","number", "Timeout in seconds",                    required=False, default=30),
                ],
                output_fields = [
                    TriggerOutputField("status_code", "number", "HTTP response status code"),
                    TriggerOutputField("body",        "any",    "Response body"),
                    TriggerOutputField("success",     "boolean","True if status < 400"),
                ],
            ),
            ActionSpec(
                id          = "put",
                name        = "PUT Request",
                description = "Make an HTTP PUT request.",
                icon        = "🔄",
                idempotent  = True,
                input_fields = [
                    ActionInputField("url",    "string", "Request URL",         required=True),
                    ActionInputField("body",   "object", "Request body (JSON)", required=False),
                    ActionInputField("headers","object", "Extra headers",       required=False),
                ],
                output_fields = [
                    TriggerOutputField("status_code", "number", "HTTP status"),
                    TriggerOutputField("body",        "any",    "Response body"),
                ],
            ),
            ActionSpec(
                id          = "patch",
                name        = "PATCH Request",
                description = "Make an HTTP PATCH request.",
                icon        = "✏️",
                idempotent  = True,
                input_fields = [
                    ActionInputField("url",    "string", "Request URL",                       required=True),
                    ActionInputField("body",   "object", "Partial update body (JSON)",        required=False),
                    ActionInputField("headers","object", "Extra headers",                     required=False),
                ],
                output_fields = [
                    TriggerOutputField("status_code", "number", "HTTP status"),
                    TriggerOutputField("body",        "any",    "Response body"),
                ],
            ),
            ActionSpec(
                id          = "delete",
                name        = "DELETE Request",
                description = "Make an HTTP DELETE request.",
                icon        = "🗑️",
                idempotent  = True,
                input_fields = [
                    ActionInputField("url",    "string", "Request URL", required=True),
                    ActionInputField("headers","object", "Extra headers", required=False),
                ],
                output_fields = [
                    TriggerOutputField("status_code", "number", "HTTP status"),
                    TriggerOutputField("success",     "boolean","True if status < 400"),
                ],
            ),
            ActionSpec(
                id          = "graphql",
                name        = "GraphQL Query",
                description = "Execute a GraphQL query or mutation.",
                icon        = "🔷",
                idempotent  = False,
                input_fields = [
                    ActionInputField("url",       "string", "GraphQL endpoint URL",                          required=True),
                    ActionInputField("query",     "string", "GraphQL query or mutation string",              required=True),
                    ActionInputField("variables", "object", "GraphQL variables",                             required=False),
                    ActionInputField("headers",   "object", "Extra headers (Authorization, etc.)",           required=False),
                ],
                output_fields = [
                    TriggerOutputField("data",   "object", "GraphQL response data"),
                    TriggerOutputField("errors", "array",  "GraphQL errors (if any)"),
                ],
            ),
        ],

        config = [
            ConfigField(
                name        = "base_url",
                label       = "Base URL",
                type        = FieldType.URL,
                required    = False,
                placeholder = "https://api.example.com",
                help_text   = "Base URL prepended to all relative URLs in actions.",
            ),
            ConfigField(
                name        = "auth_type",
                label       = "Authentication Type",
                type        = FieldType.SELECT,
                required    = False,
                default     = "none",
                options     = ["none", "api_key", "bearer", "basic"],
            ),
            ConfigField(
                name        = "api_key_header",
                label       = "API Key Header Name",
                type        = FieldType.STRING,
                required    = False,
                default     = "X-API-Key",
                depends_on  = "auth_type",
                help_text   = "Header name to send the API key in.",
            ),
            ConfigField(
                name        = "default_headers",
                label       = "Default Headers (JSON)",
                type        = FieldType.TEXTAREA,
                required    = False,
                placeholder = '{"Content-Type": "application/json"}',
                help_text   = "JSON object of headers to include in every request.",
            ),
            ConfigField(
                name        = "timeout_seconds",
                label       = "Default Timeout (seconds)",
                type        = FieldType.NUMBER,
                required    = False,
                default     = 30,
            ),
        ],

        permissions = [
            Permission(PermissionScope.READ,  "http_endpoints", "Make HTTP GET requests to external APIs"),
            Permission(PermissionScope.WRITE, "http_endpoints", "Make HTTP POST/PUT/PATCH/DELETE requests"),
            Permission(PermissionScope.WEBHOOK, "webhooks",     "Receive incoming webhook requests"),
        ],
    )

    def get_auth_provider(self):
        return NoAuthProvider()

    def _build_headers(self, ctx: PluginContext, extra: Dict = None) -> Dict[str, str]:
        import json
        headers: Dict[str, str] = {}
        # Default headers from config
        try:
            default_h = json.loads(ctx.get_config("default_headers") or "{}")
            headers.update(default_h)
        except Exception:
            pass

        # Auth headers
        auth_type = ctx.get_config("auth_type", "none")
        if auth_type == "api_key":
            key = ctx.secret("PLUGIN_API_KEY") or ""
            header = ctx.get_config("api_key_header", "X-API-Key")
            if key:
                headers[header] = key
        elif auth_type == "bearer":
            token = ctx.secret("PLUGIN_BEARER_TOKEN") or ""
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "basic":
            import base64
            user = ctx.secret("PLUGIN_USERNAME") or ""
            pwd  = ctx.secret("PLUGIN_PASSWORD") or ""
            if user:
                encoded = base64.b64encode(f"{user}:{pwd}".encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"

        if extra:
            headers.update(extra)
        return headers

    def _resolve_url(self, url: str, ctx: PluginContext) -> str:
        if url.startswith("http"):
            return url
        base = ctx.get_config("base_url", "").rstrip("/")
        return f"{base}/{url.lstrip('/')}"

    def execute_action(self, action_id: str, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        errors = self.validate_action_params(action_id, params)
        if errors:
            from plugins.sdk.errors import ValidationError
            raise ValidationError(f"Invalid params for '{action_id}'", errors=errors)

        dispatch = {
            "get":     self._get,
            "post":    self._post,
            "put":     self._put,
            "patch":   self._patch,
            "delete":  self._delete,
            "graphql": self._graphql,
        }
        handler = dispatch.get(action_id)
        if not handler:
            from plugins.sdk.errors import PluginError
            raise PluginError(f"Unknown action: {action_id}")
        return handler(ctx, params)

    def _make_request(self, method: str, ctx: PluginContext, params: Dict) -> ActionResult:
        url      = self._resolve_url(params["url"], ctx)
        headers  = self._build_headers(ctx, params.get("headers"))
        timeout  = params.get("timeout_seconds") or ctx.get_config("timeout_seconds", 30)
        ctx.info(f"HTTP {method} {url}")

        if ctx.dry_run:
            return ActionResult.ok(data={"status_code": 200, "body": {"simulated": True, "method": method, "url": url}, "headers": {}, "success": True})

        from plugins.sdk.errors import NetworkError
        try:
            import httpx
            kw: Dict[str, Any] = {"headers": headers, "timeout": timeout, "follow_redirects": params.get("follow_redirects", True)}
            if params.get("body"):           kw["json"]   = params["body"]
            if params.get("form_data"):      kw["data"]   = params["form_data"]
            if params.get("query_params"):   kw["params"] = params["query_params"]
            with httpx.Client() as client:
                resp = client.request(method, url, **kw)
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            return ActionResult.ok(data={"status_code": resp.status_code, "body": body, "headers": dict(resp.headers), "success": resp.status_code < 400})
        except Exception as exc:
            raise NetworkError(str(exc)) from exc

    @action(id="get", name="GET Request", icon="📥", idempotent=True)
    def _get(self, ctx: PluginContext, params: Dict) -> ActionResult:
        return self._make_request("GET", ctx, params)

    @action(id="post", name="POST Request", icon="📤")
    def _post(self, ctx: PluginContext, params: Dict) -> ActionResult:
        return self._make_request("POST", ctx, params)

    @action(id="put", name="PUT Request", icon="🔄")
    def _put(self, ctx: PluginContext, params: Dict) -> ActionResult:
        return self._make_request("PUT", ctx, params)

    @action(id="patch", name="PATCH Request", icon="✏️")
    def _patch(self, ctx: PluginContext, params: Dict) -> ActionResult:
        return self._make_request("PATCH", ctx, params)

    @action(id="delete", name="DELETE Request", icon="🗑️")
    def _delete(self, ctx: PluginContext, params: Dict) -> ActionResult:
        return self._make_request("DELETE", ctx, params)

    @action(id="graphql", name="GraphQL Query", icon="🔷")
    def _graphql(self, ctx: PluginContext, params: Dict) -> ActionResult:
        url     = self._resolve_url(params["url"], ctx)
        headers = self._build_headers(ctx, params.get("headers"))
        ctx.info(f"GraphQL query to {url}")
        if ctx.dry_run:
            return ActionResult.ok(data={"data": {"simulated": True}, "errors": []})
        payload = {"query": params["query"]}
        if params.get("variables"):
            payload["variables"] = params["variables"]
        from plugins.sdk.errors import NetworkError
        try:
            import httpx
            with httpx.Client() as client:
                resp = client.post(url, json=payload, headers=headers, timeout=30)
                body = resp.json()
            return ActionResult.ok(data={"data": body.get("data"), "errors": body.get("errors", [])})
        except Exception as exc:
            raise NetworkError(str(exc)) from exc

    def handle_webhook(self, trigger_id: str, ctx: PluginContext, payload: Dict, headers: Dict) -> List[TriggerEvent]:
        if trigger_id == "webhook_receiver":
            return [TriggerEvent(trigger_id=trigger_id, plugin_id=self.manifest.id, payload={"payload": payload, "headers": headers})]
        return []

    def on_test(self, ctx: PluginContext) -> ActionResult:
        url = ctx.get_config("base_url") or "https://httpbin.org/get"
        return self.execute_action("get", ctx, {"url": url})
