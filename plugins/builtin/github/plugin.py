"""
GitHub Plugin
=============
Manifest  : GitHub repository and workflow automation
Auth      : Bearer token (Personal Access Token or GitHub App token)
Triggers  : Push, Pull Request, Issue, Release, Workflow Run, Star
Actions   : Create Issue, Comment on PR, Create Release, Trigger Workflow,
            Merge PR, Add Label, Create Branch, Get File Content
Icon      : 🐙
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
    LifecycleHook, LifecycleEvent,
    PluginContext, ActionResult, TriggerEvent,
    BearerTokenProvider,
    action, trigger, on_install,
)

_GITHUB_API = "https://api.github.com"


class Plugin(BasePlugin):
    """GitHub plugin — repositories, issues, pull requests, workflows."""

    manifest = PluginManifest(
        id          = "github",
        name        = "GitHub",
        version     = "1.0.0",
        description = "Automate GitHub workflows: react to push events, manage issues and pull requests, trigger CI/CD pipelines, and create releases.",
        author      = "Automation Platform Team",
        homepage    = "https://github.com",
        docs_url    = "https://docs.automation.platform/plugins/github",
        license     = "MIT",
        icon        = "🐙",
        icon_bg     = "#24292e",
        color       = "#24292e",
        categories  = ["DevOps", "Version Control", "CI/CD"],
        tags        = ["github", "git", "devops", "pull-request", "issues", "ci-cd"],

        auth = AuthConfig(
            type        = AuthType.BEARER,
            label       = "Connect GitHub Account",
            api_key_env = "GITHUB_TOKEN",
            help_url    = "https://github.com/settings/tokens",
            help_text   = "Generate a Personal Access Token with repo, workflow, and issues scopes.",
            setup_steps = [
                "Go to GitHub → Settings → Developer Settings → Personal Access Tokens",
                "Generate a token with scopes: repo, workflow, issues, pull_requests",
                "Set GITHUB_TOKEN environment variable",
            ],
        ),

        triggers = [
            TriggerSpec(
                id          = "push",
                name        = "New Push",
                description = "Fires when commits are pushed to a branch.",
                type        = TriggerType.WEBHOOK,
                webhook_path= "/webhooks/github",
                icon        = "⬆️",
                output_fields = [
                    TriggerOutputField("repository",  "string", "repo full name"),
                    TriggerOutputField("branch",      "string", "Branch ref"),
                    TriggerOutputField("commit_sha",  "string", "Latest commit SHA"),
                    TriggerOutputField("commit_msg",  "string", "Commit message"),
                    TriggerOutputField("pusher",      "string", "GitHub username of pusher"),
                    TriggerOutputField("compare_url", "string", "URL comparing before/after"),
                ],
            ),
            TriggerSpec(
                id          = "pull_request",
                name        = "Pull Request Event",
                description = "Fires on PR opened, closed, merged, or review requested.",
                type        = TriggerType.WEBHOOK,
                webhook_path= "/webhooks/github",
                icon        = "🔀",
                output_fields = [
                    TriggerOutputField("action",     "string", "opened|closed|synchronize|review_requested"),
                    TriggerOutputField("pr_number",  "number", "PR number"),
                    TriggerOutputField("pr_title",   "string", "PR title"),
                    TriggerOutputField("pr_url",     "string", "PR web URL"),
                    TriggerOutputField("author",     "string", "PR author username"),
                    TriggerOutputField("base_branch","string", "Target branch"),
                    TriggerOutputField("head_branch","string", "Source branch"),
                    TriggerOutputField("merged",     "boolean","Whether PR was merged"),
                ],
            ),
            TriggerSpec(
                id          = "issue",
                name        = "Issue Event",
                description = "Fires when an issue is opened, closed, or labelled.",
                type        = TriggerType.WEBHOOK,
                webhook_path= "/webhooks/github",
                icon        = "🐛",
                output_fields = [
                    TriggerOutputField("action",     "string", "opened|closed|labeled|assigned"),
                    TriggerOutputField("issue_number","number", "Issue number"),
                    TriggerOutputField("issue_title","string", "Issue title"),
                    TriggerOutputField("issue_url",  "string", "Issue web URL"),
                    TriggerOutputField("author",     "string", "Issue author"),
                    TriggerOutputField("labels",     "array",  "List of label names"),
                ],
            ),
            TriggerSpec(
                id          = "release",
                name        = "New Release Published",
                description = "Fires when a new release is published.",
                type        = TriggerType.WEBHOOK,
                webhook_path= "/webhooks/github",
                icon        = "🚀",
                output_fields = [
                    TriggerOutputField("tag_name",    "string", "Release tag"),
                    TriggerOutputField("release_name","string", "Release title"),
                    TriggerOutputField("release_url", "string", "Release web URL"),
                    TriggerOutputField("prerelease",  "boolean","True if pre-release"),
                    TriggerOutputField("body",        "string", "Release notes"),
                ],
            ),
            TriggerSpec(
                id          = "workflow_run",
                name        = "Workflow Run Completed",
                description = "Fires when a GitHub Actions workflow completes.",
                type        = TriggerType.WEBHOOK,
                webhook_path= "/webhooks/github",
                icon        = "⚙️",
                output_fields = [
                    TriggerOutputField("workflow_name","string", "Workflow name"),
                    TriggerOutputField("conclusion",  "string", "success|failure|cancelled|skipped"),
                    TriggerOutputField("run_id",      "number", "Workflow run ID"),
                    TriggerOutputField("run_url",     "string", "Workflow run URL"),
                    TriggerOutputField("branch",      "string", "Branch the workflow ran on"),
                ],
            ),
        ],

        actions = [
            ActionSpec(
                id          = "create_issue",
                name        = "Create Issue",
                description = "Create a new GitHub issue in a repository.",
                icon        = "➕",
                idempotent  = False,
                input_fields = [
                    ActionInputField("owner",  "string", "Repository owner (user or org)", required=True),
                    ActionInputField("repo",   "string", "Repository name",                required=True),
                    ActionInputField("title",  "string", "Issue title",                   required=True),
                    ActionInputField("body",   "string", "Issue description (markdown)",   required=False),
                    ActionInputField("labels", "array",  "List of label names",            required=False),
                    ActionInputField("assignees","array","List of assignee usernames",     required=False),
                ],
                output_fields = [
                    TriggerOutputField("issue_number", "number", "New issue number"),
                    TriggerOutputField("issue_url",    "string", "Issue web URL"),
                    TriggerOutputField("issue_id",     "number", "Issue node ID"),
                ],
            ),
            ActionSpec(
                id          = "create_comment",
                name        = "Create Comment",
                description = "Add a comment to an issue or pull request.",
                icon        = "💬",
                idempotent  = False,
                input_fields = [
                    ActionInputField("owner",        "string", "Repository owner",    required=True),
                    ActionInputField("repo",         "string", "Repository name",     required=True),
                    ActionInputField("issue_number", "number", "Issue or PR number",  required=True),
                    ActionInputField("body",         "string", "Comment text",        required=True),
                ],
                output_fields = [
                    TriggerOutputField("comment_id",  "number", "Comment ID"),
                    TriggerOutputField("comment_url", "string", "Comment URL"),
                ],
            ),
            ActionSpec(
                id          = "create_release",
                name        = "Create Release",
                description = "Create a new GitHub release with optional assets.",
                icon        = "🚀",
                idempotent  = False,
                input_fields = [
                    ActionInputField("owner",      "string",  "Repository owner",  required=True),
                    ActionInputField("repo",       "string",  "Repository name",   required=True),
                    ActionInputField("tag_name",   "string",  "Release tag",       required=True),
                    ActionInputField("name",       "string",  "Release title",     required=False),
                    ActionInputField("body",       "string",  "Release notes",     required=False),
                    ActionInputField("prerelease", "boolean", "Mark as pre-release",required=False, default=False),
                    ActionInputField("draft",      "boolean", "Create as draft",   required=False, default=False),
                ],
                output_fields = [
                    TriggerOutputField("release_id",  "number", "Release ID"),
                    TriggerOutputField("release_url", "string", "Release page URL"),
                    TriggerOutputField("upload_url",  "string", "URL for asset uploads"),
                ],
            ),
            ActionSpec(
                id          = "trigger_workflow",
                name        = "Trigger Workflow",
                description = "Manually dispatch a GitHub Actions workflow.",
                icon        = "▶️",
                idempotent  = False,
                input_fields = [
                    ActionInputField("owner",       "string", "Repository owner",    required=True),
                    ActionInputField("repo",        "string", "Repository name",     required=True),
                    ActionInputField("workflow_id", "string", "Workflow file name or ID", required=True),
                    ActionInputField("ref",         "string", "Branch or tag to run on", required=True, default="main"),
                    ActionInputField("inputs",      "object", "Workflow input values",    required=False),
                ],
                output_fields = [],
            ),
            ActionSpec(
                id          = "add_label",
                name        = "Add Label to Issue/PR",
                description = "Add one or more labels to an issue or pull request.",
                icon        = "🏷️",
                idempotent  = True,
                input_fields = [
                    ActionInputField("owner",        "string", "Repository owner",   required=True),
                    ActionInputField("repo",         "string", "Repository name",    required=True),
                    ActionInputField("issue_number", "number", "Issue or PR number", required=True),
                    ActionInputField("labels",       "array",  "Label names to add", required=True),
                ],
                output_fields = [
                    TriggerOutputField("labels", "array", "All current labels"),
                ],
            ),
            ActionSpec(
                id          = "get_file",
                name        = "Get File Content",
                description = "Fetch the content of a file from a repository.",
                icon        = "📄",
                readonly    = True,
                idempotent  = True,
                input_fields = [
                    ActionInputField("owner", "string", "Repository owner", required=True),
                    ActionInputField("repo",  "string", "Repository name",  required=True),
                    ActionInputField("path",  "string", "File path in repo",required=True),
                    ActionInputField("ref",   "string", "Branch or commit", required=False, default="main"),
                ],
                output_fields = [
                    TriggerOutputField("content",  "string", "File content (decoded)"),
                    TriggerOutputField("sha",      "string", "File blob SHA"),
                    TriggerOutputField("size",     "number", "File size in bytes"),
                    TriggerOutputField("html_url", "string", "File URL on GitHub"),
                ],
            ),
        ],

        config = [
            ConfigField(
                name        = "default_owner",
                label       = "Default Repository Owner",
                type        = FieldType.STRING,
                required    = False,
                placeholder = "myorg",
                help_text   = "Default GitHub user or org when none is specified.",
            ),
            ConfigField(
                name        = "default_repo",
                label       = "Default Repository",
                type        = FieldType.STRING,
                required    = False,
                placeholder = "my-repo",
            ),
            ConfigField(
                name        = "webhook_secret",
                label       = "Webhook Secret",
                type        = FieldType.PASSWORD,
                required    = False,
                sensitive   = True,
                help_text   = "Secret used to verify incoming GitHub webhook payloads.",
            ),
        ],

        permissions = [
            Permission(PermissionScope.READ,    "repositories", "Read repository content and metadata"),
            Permission(PermissionScope.WRITE,   "issues",       "Create and update issues"),
            Permission(PermissionScope.WRITE,   "pull_requests","Comment on and label pull requests"),
            Permission(PermissionScope.WRITE,   "releases",     "Create and publish releases"),
            Permission(PermissionScope.WRITE,   "workflows",    "Trigger GitHub Actions workflows"),
            Permission(PermissionScope.WEBHOOK, "events",       "Receive webhook events"),
        ],
    )

    def get_auth_provider(self):
        return BearerTokenProvider("GITHUB_TOKEN")

    def _headers(self, ctx: PluginContext) -> Dict:
        token = ctx.require_secret("GITHUB_TOKEN")
        return {
            "Authorization": f"Bearer {token}",
            "Accept":        "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def execute_action(self, action_id: str, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        errors = self.validate_action_params(action_id, params)
        if errors:
            from plugins.sdk.errors import ValidationError
            raise ValidationError(f"Invalid params for '{action_id}'", errors=errors)

        dispatch = {
            "create_issue":    self._create_issue,
            "create_comment":  self._create_comment,
            "create_release":  self._create_release,
            "trigger_workflow":self._trigger_workflow,
            "add_label":       self._add_label,
            "get_file":        self._get_file,
        }
        handler = dispatch.get(action_id)
        if not handler:
            from plugins.sdk.errors import PluginError
            raise PluginError(f"Unknown action: {action_id}")
        return handler(ctx, params)

    @action(id="create_issue", name="Create Issue", icon="➕")
    def _create_issue(self, ctx: PluginContext, params: Dict) -> ActionResult:
        owner, repo = params["owner"], params["repo"]
        ctx.info(f"Creating issue in {owner}/{repo}: {params['title']}")
        if ctx.dry_run:
            return ActionResult.ok(data={"issue_number": 999, "issue_url": f"https://github.com/{owner}/{repo}/issues/999"})
        body: Dict[str, Any] = {"title": params["title"]}
        if params.get("body"):    body["body"]      = params["body"]
        if params.get("labels"):  body["labels"]    = params["labels"]
        if params.get("assignees"):body["assignees"]= params["assignees"]
        result = ctx.http_post(f"{_GITHUB_API}/repos/{owner}/{repo}/issues", json=body, headers=self._headers(ctx))
        return ActionResult.ok(data={"issue_number": result["number"], "issue_url": result["html_url"]})

    @action(id="create_comment", name="Create Comment", icon="💬")
    def _create_comment(self, ctx: PluginContext, params: Dict) -> ActionResult:
        owner, repo, num = params["owner"], params["repo"], params["issue_number"]
        ctx.info(f"Adding comment to {owner}/{repo}#{num}")
        if ctx.dry_run:
            return ActionResult.ok(data={"comment_id": 9999, "comment_url": f"https://github.com/{owner}/{repo}/issues/{num}#issuecomment-9999"})
        result = ctx.http_post(
            f"{_GITHUB_API}/repos/{owner}/{repo}/issues/{num}/comments",
            json={"body": params["body"]},
            headers=self._headers(ctx),
        )
        return ActionResult.ok(data={"comment_id": result["id"], "comment_url": result["html_url"]})

    @action(id="create_release", name="Create Release", icon="🚀")
    def _create_release(self, ctx: PluginContext, params: Dict) -> ActionResult:
        owner, repo = params["owner"], params["repo"]
        ctx.info(f"Creating release {params['tag_name']} in {owner}/{repo}")
        if ctx.dry_run:
            return ActionResult.ok(data={"release_id": 9999, "release_url": f"https://github.com/{owner}/{repo}/releases/tag/{params['tag_name']}"})
        body = {
            "tag_name":   params["tag_name"],
            "name":       params.get("name", params["tag_name"]),
            "body":       params.get("body", ""),
            "prerelease": params.get("prerelease", False),
            "draft":      params.get("draft", False),
        }
        result = ctx.http_post(f"{_GITHUB_API}/repos/{owner}/{repo}/releases", json=body, headers=self._headers(ctx))
        return ActionResult.ok(data={"release_id": result["id"], "release_url": result["html_url"], "upload_url": result.get("upload_url")})

    @action(id="trigger_workflow", name="Trigger Workflow", icon="▶️")
    def _trigger_workflow(self, ctx: PluginContext, params: Dict) -> ActionResult:
        owner, repo, wf = params["owner"], params["repo"], params["workflow_id"]
        ctx.info(f"Triggering workflow {wf} in {owner}/{repo}")
        if ctx.dry_run:
            return ActionResult.ok(data={"message": f"Workflow {wf} would be triggered"})
        ctx.http_post(
            f"{_GITHUB_API}/repos/{owner}/{repo}/actions/workflows/{wf}/dispatches",
            json={"ref": params.get("ref", "main"), "inputs": params.get("inputs", {})},
            headers=self._headers(ctx),
        )
        return ActionResult.ok(data={"message": f"Workflow '{wf}' dispatched on '{params.get('ref', 'main')}'"})

    @action(id="add_label", name="Add Label", icon="🏷️")
    def _add_label(self, ctx: PluginContext, params: Dict) -> ActionResult:
        owner, repo, num = params["owner"], params["repo"], params["issue_number"]
        ctx.info(f"Adding labels {params['labels']} to {owner}/{repo}#{num}")
        if ctx.dry_run:
            return ActionResult.ok(data={"labels": params["labels"]})
        result = ctx.http_post(
            f"{_GITHUB_API}/repos/{owner}/{repo}/issues/{num}/labels",
            json={"labels": params["labels"]},
            headers=self._headers(ctx),
        )
        return ActionResult.ok(data={"labels": [l["name"] for l in result]})

    @action(id="get_file", name="Get File Content", icon="📄", readonly=True, idempotent=True)
    def _get_file(self, ctx: PluginContext, params: Dict) -> ActionResult:
        import base64
        owner, repo = params["owner"], params["repo"]
        path        = params["path"]
        ref         = params.get("ref", "main")
        ctx.info(f"Getting {owner}/{repo}/{path}@{ref}")
        if ctx.dry_run:
            return ActionResult.ok(data={"content": "# Simulated file content\n", "sha": "abc123"})
        result = ctx.http_get(
            f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
            headers=self._headers(ctx),
        )
        content = base64.b64decode(result["content"]).decode("utf-8", errors="replace")
        return ActionResult.ok(data={"content": content, "sha": result["sha"], "size": result["size"], "html_url": result["html_url"]})

    def handle_webhook(self, trigger_id: str, ctx: PluginContext, payload: Dict, headers: Dict) -> List[TriggerEvent]:
        event = headers.get("X-GitHub-Event", "")
        events: List[TriggerEvent] = []
        if event == "push" and trigger_id == "push":
            events.append(TriggerEvent(trigger_id=trigger_id, plugin_id=self.manifest.id, payload={
                "repository": payload.get("repository", {}).get("full_name"),
                "branch":     payload.get("ref"),
                "commit_sha": payload.get("after"),
                "commit_msg": payload.get("head_commit", {}).get("message"),
                "pusher":     payload.get("pusher", {}).get("name"),
            }))
        elif event == "pull_request" and trigger_id == "pull_request":
            pr = payload.get("pull_request", {})
            events.append(TriggerEvent(trigger_id=trigger_id, plugin_id=self.manifest.id, payload={
                "action":    payload.get("action"),
                "pr_number": pr.get("number"),
                "pr_title":  pr.get("title"),
                "pr_url":    pr.get("html_url"),
                "author":    pr.get("user", {}).get("login"),
                "merged":    pr.get("merged", False),
            }))
        return events

    def on_test(self, ctx: PluginContext) -> ActionResult:
        if ctx.dry_run:
            return ActionResult.ok(data={"message": "GitHub plugin test passed (dry-run)"})
        try:
            result = ctx.http_get(f"{_GITHUB_API}/user", headers=self._headers(ctx))
            return ActionResult.ok(data={"login": result.get("login"), "message": "Connected to GitHub"})
        except Exception as exc:
            return ActionResult.fail(str(exc))
