from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AIResponse:
    feedback: str
    hints: list[str]


class AIProvider:
    def generate(self, *, prompt: str) -> AIResponse:  # pragma: no cover
        raise NotImplementedError


class NullAIProvider(AIProvider):
    def generate(self, *, prompt: str) -> AIResponse:
        return AIResponse(
            feedback="AI feedback not configured; using rule-based feedback.",
            hints=[],
        )


class OpenAIChatCompletionsProvider(AIProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, *, prompt: str) -> AIResponse:
        # Prefer the OpenAI SDK Responses API (works with modern models like gpt-5).
        # Fallback to HTTP Chat Completions only if SDK isn't available.
        timeout_s = 20
        try:
            timeout_s = int(os.getenv("OPENAI_TIMEOUT_S", "20").strip() or "20")
        except Exception:
            timeout_s = 20

        system_msg = "You are a teaching assistant. Give hints without revealing full solutions."
        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=self.api_key)
            resp = client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                timeout=timeout_s,
            )
            content = getattr(resp, "output_text", "") or ""
        except Exception:
            # Lightweight HTTP call to OpenAI Chat Completions API.
            # Some models may not support this endpoint; if so, we fall back to rule-based feedback.
            import json
            import urllib.request

            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", method="POST")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            req.add_header("Content-Type", "application/json")
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            }
            data = json.dumps(payload).encode("utf-8")
            try:
                with urllib.request.urlopen(req, data=data, timeout=timeout_s) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                obj = json.loads(body)
                content = obj["choices"][0]["message"]["content"]
            except Exception:
                return AIResponse(feedback="AI provider call failed; using rule-based feedback.", hints=[])

        # Very simple split: first paragraph is feedback, rest are hints.
        lines = [ln.strip() for ln in str(content).splitlines() if ln.strip()]
        feedback = lines[0] if lines else "AI feedback generated."
        hints = lines[1:6] if len(lines) > 1 else []
        return AIResponse(feedback=feedback, hints=hints)


def get_ai_provider() -> AIProvider:
    # Placeholder hook: later you can add a real provider and select via env vars.
    # For now we always return NullAIProvider so the platform runs offline.
    provider = os.getenv("AI_PROVIDER", "null").strip().lower()
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        if api_key:
            return OpenAIChatCompletionsProvider(api_key=api_key, model=model)
    return NullAIProvider()
