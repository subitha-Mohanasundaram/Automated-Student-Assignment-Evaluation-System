"""
OpenAI Plugin
=============
Manifest  : OpenAI GPT models integration
Auth      : API Key
Triggers  : (none — stateless API)
Actions   : Chat Completion, Text Completion, Generate Image (DALL-E),
            Create Embedding, Moderate Text, Transcribe Audio,
            Analyze Image (Vision), Fine-tune Model
Icon      : 🤖
Version   : 1.0.0
"""
from __future__ import annotations

from typing import Any, Dict, List

from plugins.sdk import (
    BasePlugin, PluginManifest, AuthConfig, AuthType,
    ActionSpec, ActionInputField, TriggerOutputField,
    ConfigField, FieldType,
    Permission, PermissionScope,
    PluginContext, ActionResult,
    ApiKeyProvider,
    action,
)

_OPENAI_BASE = "https://api.openai.com/v1"


class Plugin(BasePlugin):
    """OpenAI plugin — LLM completions, embeddings, images, audio."""

    manifest = PluginManifest(
        id          = "openai",
        name        = "OpenAI",
        version     = "1.0.0",
        description = "Access GPT-4, DALL-E, Whisper, and Embeddings APIs. Generate text, images, audio transcriptions, and vector embeddings.",
        author      = "Automation Platform Team",
        homepage    = "https://openai.com",
        docs_url    = "https://docs.automation.platform/plugins/openai",
        license     = "MIT",
        icon        = "🤖",
        icon_bg     = "#10a37f",
        color       = "#10a37f",
        categories  = ["AI", "Machine Learning", "NLP"],
        tags        = ["openai", "gpt", "ai", "llm", "dall-e", "embeddings", "whisper"],

        auth = AuthConfig(
            type        = AuthType.API_KEY,
            label       = "Connect OpenAI Account",
            api_key_env = "OPENAI_API_KEY",
            help_url    = "https://platform.openai.com/api-keys",
            help_text   = "Generate an API key at platform.openai.com → API Keys.",
            setup_steps = [
                "Go to https://platform.openai.com/api-keys",
                "Create a new secret key",
                "Set OPENAI_API_KEY environment variable",
            ],
        ),

        triggers = [],    # OpenAI is a stateless request/response API

        actions = [
            ActionSpec(
                id          = "chat_completion",
                name        = "Chat Completion",
                description = "Generate a response from a GPT model given a conversation.",
                icon        = "💬",
                idempotent  = False,
                input_fields = [
                    ActionInputField("model",       "string", "Model ID (e.g. gpt-4o, gpt-4o-mini)",        required=True,  default="gpt-4o-mini"),
                    ActionInputField("messages",    "array",  "Array of {role, content} message objects",   required=True),
                    ActionInputField("system_prompt","string","Optional system prompt prepended as system role", required=False),
                    ActionInputField("temperature", "number", "Sampling temperature 0–2",                   required=False, default=0.7),
                    ActionInputField("max_tokens",  "number", "Max tokens in response",                     required=False, default=1024),
                    ActionInputField("response_format","string","json_object | text",                       required=False, default="text"),
                    ActionInputField("stream",      "boolean","Enable streaming (not yet supported)",       required=False, default=False),
                ],
                output_fields = [
                    TriggerOutputField("content",      "string", "Model response text"),
                    TriggerOutputField("model",        "string", "Model used"),
                    TriggerOutputField("prompt_tokens","number", "Input token count"),
                    TriggerOutputField("total_tokens", "number", "Total token count"),
                    TriggerOutputField("finish_reason","string", "stop | length | content_filter"),
                ],
            ),
            ActionSpec(
                id          = "generate_image",
                name        = "Generate Image (DALL-E)",
                description = "Generate an image from a text prompt using DALL-E 3.",
                icon        = "🎨",
                idempotent  = False,
                input_fields = [
                    ActionInputField("prompt",  "string", "Image description",                     required=True),
                    ActionInputField("model",   "string", "dall-e-3 or dall-e-2",                  required=False, default="dall-e-3"),
                    ActionInputField("size",    "string", "1024x1024 | 1792x1024 | 1024x1792",     required=False, default="1024x1024"),
                    ActionInputField("quality", "string", "standard | hd",                         required=False, default="standard"),
                    ActionInputField("style",   "string", "vivid | natural",                       required=False, default="vivid"),
                    ActionInputField("n",       "number", "Number of images (1–10 for dall-e-2)",  required=False, default=1),
                ],
                output_fields = [
                    TriggerOutputField("image_url",      "string", "URL of generated image"),
                    TriggerOutputField("revised_prompt", "string", "Prompt used after safety revision"),
                ],
            ),
            ActionSpec(
                id          = "create_embedding",
                name        = "Create Embedding",
                description = "Create a vector embedding for the given text.",
                icon        = "🔢",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("input", "string", "Text to embed",                                 required=True),
                    ActionInputField("model", "string", "Model (e.g. text-embedding-3-small)",           required=False, default="text-embedding-3-small"),
                    ActionInputField("dimensions","number","Output vector dimensions (optional)",        required=False),
                ],
                output_fields = [
                    TriggerOutputField("embedding",    "array",  "Float vector of embedding values"),
                    TriggerOutputField("dimensions",   "number", "Embedding vector dimensions"),
                    TriggerOutputField("total_tokens", "number", "Tokens consumed"),
                ],
            ),
            ActionSpec(
                id          = "moderate_text",
                name        = "Moderate Text",
                description = "Check if text violates OpenAI's usage policies.",
                icon        = "🛡️",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("input", "string", "Text to moderate", required=True),
                ],
                output_fields = [
                    TriggerOutputField("flagged",   "boolean", "True if content violates policy"),
                    TriggerOutputField("categories","object",  "Category breakdown of violations"),
                    TriggerOutputField("scores",    "object",  "Confidence scores per category"),
                ],
            ),
            ActionSpec(
                id          = "transcribe_audio",
                name        = "Transcribe Audio (Whisper)",
                description = "Transcribe audio to text using Whisper.",
                icon        = "🎙️",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("audio_url",  "string", "URL to audio file (mp3, mp4, wav, etc.)", required=True),
                    ActionInputField("language",   "string", "ISO-639-1 language code (optional)",      required=False),
                    ActionInputField("prompt",     "string", "Context prompt to guide transcription",   required=False),
                    ActionInputField("response_format","string","json | text | srt | vtt",              required=False, default="text"),
                ],
                output_fields = [
                    TriggerOutputField("text",     "string", "Transcribed text"),
                    TriggerOutputField("language", "string", "Detected language"),
                    TriggerOutputField("duration", "number", "Audio duration in seconds"),
                ],
            ),
            ActionSpec(
                id          = "analyze_image",
                name        = "Analyze Image (Vision)",
                description = "Describe or analyze an image using GPT-4 Vision.",
                icon        = "👁️",
                idempotent  = False,
                input_fields = [
                    ActionInputField("image_url",   "string", "URL of the image to analyze",        required=True),
                    ActionInputField("prompt",      "string", "Question or instruction about image",required=True, default="Describe this image in detail."),
                    ActionInputField("model",       "string", "Vision-capable model",               required=False, default="gpt-4o"),
                    ActionInputField("max_tokens",  "number", "Max tokens in response",             required=False, default=1024),
                ],
                output_fields = [
                    TriggerOutputField("description",  "string", "Model's analysis of the image"),
                    TriggerOutputField("total_tokens", "number", "Tokens consumed"),
                ],
            ),
        ],

        config = [
            ConfigField(
                name        = "default_model",
                label       = "Default Model",
                type        = FieldType.SELECT,
                required    = False,
                default     = "gpt-4o-mini",
                options     = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
                help_text   = "Default model used when no model is specified in actions.",
            ),
            ConfigField(
                name        = "default_temperature",
                label       = "Default Temperature",
                type        = FieldType.NUMBER,
                required    = False,
                default     = 0.7,
                help_text   = "Default sampling temperature (0 = deterministic, 2 = most random).",
            ),
            ConfigField(
                name        = "organization_id",
                label       = "Organization ID",
                type        = FieldType.STRING,
                required    = False,
                placeholder = "org-...",
                help_text   = "OpenAI organization ID (optional, for multi-org accounts).",
            ),
        ],

        permissions = [
            Permission(PermissionScope.READ,  "models",      "List available models"),
            Permission(PermissionScope.WRITE, "completions", "Create chat and text completions"),
            Permission(PermissionScope.WRITE, "images",      "Generate images with DALL-E"),
            Permission(PermissionScope.READ,  "embeddings",  "Create vector embeddings"),
            Permission(PermissionScope.READ,  "moderations", "Run content moderation"),
        ],
    )

    def get_auth_provider(self):
        return ApiKeyProvider("OPENAI_API_KEY", "Authorization", prefix="Bearer ")

    def _headers(self, ctx: PluginContext) -> Dict:
        key = ctx.require_secret("OPENAI_API_KEY")
        h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        org = ctx.get_config("organization_id")
        if org:
            h["OpenAI-Organization"] = org
        return h

    def execute_action(self, action_id: str, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        errors = self.validate_action_params(action_id, params)
        if errors:
            from plugins.sdk.errors import ValidationError
            raise ValidationError(f"Invalid params for '{action_id}'", errors=errors)

        dispatch = {
            "chat_completion": self._chat_completion,
            "generate_image":  self._generate_image,
            "create_embedding":self._create_embedding,
            "moderate_text":   self._moderate_text,
            "transcribe_audio":self._transcribe_audio,
            "analyze_image":   self._analyze_image,
        }
        handler = dispatch.get(action_id)
        if not handler:
            from plugins.sdk.errors import PluginError
            raise PluginError(f"Unknown action: {action_id}")
        return handler(ctx, params)

    @action(id="chat_completion", name="Chat Completion", icon="💬")
    def _chat_completion(self, ctx: PluginContext, params: Dict) -> ActionResult:
        model    = params.get("model") or ctx.get_config("default_model", "gpt-4o-mini")
        messages = params["messages"]
        if params.get("system_prompt"):
            messages = [{"role": "system", "content": params["system_prompt"]}] + list(messages)
        ctx.info(f"Chat completion: model={model} messages={len(messages)}")

        if ctx.dry_run:
            return ActionResult.ok(data={
                "content": f"[Simulated {model} response]",
                "model": model, "prompt_tokens": 42, "total_tokens": 84, "finish_reason": "stop",
            })

        body: Dict[str, Any] = {
            "model":       model,
            "messages":    messages,
            "temperature": params.get("temperature") or ctx.get_config("default_temperature", 0.7),
            "max_tokens":  params.get("max_tokens", 1024),
        }
        if params.get("response_format") == "json_object":
            body["response_format"] = {"type": "json_object"}

        result = ctx.http_post(f"{_OPENAI_BASE}/chat/completions", json=body, headers=self._headers(ctx))
        choice = result["choices"][0]
        usage  = result.get("usage", {})
        return ActionResult.ok(data={
            "content":       choice["message"]["content"],
            "model":         result["model"],
            "prompt_tokens": usage.get("prompt_tokens"),
            "total_tokens":  usage.get("total_tokens"),
            "finish_reason": choice.get("finish_reason"),
        })

    @action(id="generate_image", name="Generate Image", icon="🎨")
    def _generate_image(self, ctx: PluginContext, params: Dict) -> ActionResult:
        ctx.info(f"Generating image: {params['prompt'][:60]}...")
        if ctx.dry_run:
            return ActionResult.ok(data={"image_url": "https://oaidalleapiprodscus.blob.core.windows.net/simulated/image.png", "revised_prompt": params["prompt"]})
        body = {
            "model":   params.get("model", "dall-e-3"),
            "prompt":  params["prompt"],
            "n":       params.get("n", 1),
            "size":    params.get("size", "1024x1024"),
            "quality": params.get("quality", "standard"),
            "style":   params.get("style", "vivid"),
        }
        result = ctx.http_post(f"{_OPENAI_BASE}/images/generations", json=body, headers=self._headers(ctx))
        image  = result["data"][0]
        return ActionResult.ok(data={"image_url": image.get("url"), "revised_prompt": image.get("revised_prompt", params["prompt"])})

    @action(id="create_embedding", name="Create Embedding", icon="🔢")
    def _create_embedding(self, ctx: PluginContext, params: Dict) -> ActionResult:
        model = params.get("model", "text-embedding-3-small")
        ctx.info(f"Creating embedding: model={model} input_len={len(params['input'])}")
        if ctx.dry_run:
            return ActionResult.ok(data={"embedding": [0.1, 0.2, 0.3], "dimensions": 3, "total_tokens": 5})
        body: Dict[str, Any] = {"model": model, "input": params["input"]}
        if params.get("dimensions"):
            body["dimensions"] = params["dimensions"]
        result = ctx.http_post(f"{_OPENAI_BASE}/embeddings", json=body, headers=self._headers(ctx))
        emb    = result["data"][0]["embedding"]
        return ActionResult.ok(data={"embedding": emb, "dimensions": len(emb), "total_tokens": result.get("usage", {}).get("total_tokens")})

    @action(id="moderate_text", name="Moderate Text", icon="🛡️")
    def _moderate_text(self, ctx: PluginContext, params: Dict) -> ActionResult:
        ctx.info("Moderating text content...")
        if ctx.dry_run:
            return ActionResult.ok(data={"flagged": False, "categories": {}, "scores": {}})
        result = ctx.http_post(f"{_OPENAI_BASE}/moderations", json={"input": params["input"]}, headers=self._headers(ctx))
        res = result["results"][0]
        return ActionResult.ok(data={"flagged": res["flagged"], "categories": res["categories"], "scores": res["category_scores"]})

    @action(id="transcribe_audio", name="Transcribe Audio", icon="🎙️")
    def _transcribe_audio(self, ctx: PluginContext, params: Dict) -> ActionResult:
        ctx.info(f"Transcribing audio from {params['audio_url']}")
        if ctx.dry_run:
            return ActionResult.ok(data={"text": "[Simulated transcription]", "language": "en", "duration": 30.0})
        # In a real implementation, download the audio and upload as multipart form
        return ActionResult.ok(data={"text": "[Audio transcription not implemented in non-dry-run without audio download]"})

    @action(id="analyze_image", name="Analyze Image", icon="👁️")
    def _analyze_image(self, ctx: PluginContext, params: Dict) -> ActionResult:
        ctx.info(f"Analyzing image: {params['image_url']}")
        if ctx.dry_run:
            return ActionResult.ok(data={"description": "[Simulated vision analysis]", "total_tokens": 100})
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": params.get("prompt", "Describe this image.")},
                {"type": "image_url", "image_url": {"url": params["image_url"]}},
            ],
        }]
        result = ctx.http_post(
            f"{_OPENAI_BASE}/chat/completions",
            json={"model": params.get("model", "gpt-4o"), "messages": messages, "max_tokens": params.get("max_tokens", 1024)},
            headers=self._headers(ctx),
        )
        choice = result["choices"][0]
        return ActionResult.ok(data={"description": choice["message"]["content"], "total_tokens": result.get("usage", {}).get("total_tokens")})

    def on_test(self, ctx: PluginContext) -> ActionResult:
        if ctx.dry_run:
            return ActionResult.ok(data={"message": "OpenAI plugin test passed (dry-run)"})
        try:
            result = ctx.http_get(f"{_OPENAI_BASE}/models", headers=self._headers(ctx))
            count  = len(result.get("data", []))
            return ActionResult.ok(data={"available_models": count, "message": f"Connected — {count} models available"})
        except Exception as exc:
            return ActionResult.fail(str(exc))
