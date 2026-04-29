"""
Thin wrapper around the OpenAI-compatible SDK pointed at OpenRouter.

Why this layer exists
---------------------
The auditor uses the same SDK shape regardless of provider. Switching from
free OpenRouter models to a paid Anthropic/OpenAI key is a one-line change
in .env. Keeping this layer thin (no caching, no streaming) is deliberate
— a 5-hour prototype shouldn't grow infrastructure that isn't being eval'd.

Failure modes handled
---------------------
  - Rate limit / 429 / transient 5xx: retry with backoff, then fall through
    to FALLBACK_MODEL.
  - Malformed JSON in response: surfaced to caller; the pipeline turns this
    into a refusal rather than swallowing it.
  - Missing API key: clear error at startup, not on first call.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, APIError, RateLimitError

from dotenv import load_dotenv
load_dotenv()

import os
print("KEY:", os.getenv("OPENAI_API_KEY"))


PROVIDER_BASES = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    # Anthropic isn't OpenAI-compatible, so it's intentionally not in this map.
    # If you want to use Anthropic, route through OpenRouter (claude-3.5-haiku
    # etc. are available there).
}


@dataclass
class LLMResponse:
    text: str
    model: str
    raw: Any  # the SDK response object, kept for debugging


class LLMClient:
    """Single entry point for all model calls in the project."""

    def __init__(self) -> None:
        provider = os.getenv("PROVIDER", "openrouter").lower()
        if provider not in PROVIDER_BASES:
            raise RuntimeError(
                f"Unsupported PROVIDER={provider!r}. Use 'openrouter' or 'openai'."
            )

        # API key resolution: per-provider env var, falling back to OPENROUTER.
        key_var = "OPENAI_API_KEY" if provider == "openai" else "OPENROUTER_API_KEY"
        api_key = os.getenv(key_var)
        if not api_key:
            raise RuntimeError(
                f"{key_var} not set. Copy .env.example to .env and fill it in. "
                "Free OpenRouter signup: https://openrouter.ai"
            )

        self.client = OpenAI(api_key=api_key, base_url=PROVIDER_BASES[provider])
        self.primary_model = os.getenv("AUDIT_MODEL", "google/gemini-2.0-flash-exp:free")
        self.fallback_model = os.getenv(
            "FALLBACK_MODEL", "meta-llama/llama-3.2-11b-vision-instruct:free"
        )

    # ---------- public API ----------

    def complete(
        self,
        *,
        system: str,
        user: str,
        image_path: str | None = None,
        image_url: str | None = None,
        json_mode: bool = True,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """One call, optionally multimodal, optionally JSON-mode.

        We don't expose model selection to callers — the wrapper handles
        primary→fallback so the auditor stays clean.
        """
        messages = self._build_messages(
            system=system, user=user, image_path=image_path, image_url=image_url
        )
        for attempt, model in enumerate([self.primary_model, self.fallback_model]):
            try:
                resp = self._call(model, messages, json_mode, temperature, max_tokens)
                return LLMResponse(
                    text=resp.choices[0].message.content or "",
                    model=model,
                    raw=resp,
                )
            except (RateLimitError, APIError) as e:
                # Last attempt → re-raise. Otherwise log and fall through.
                if attempt == 1:
                    raise
                print(f"[client] {model} failed ({type(e).__name__}); falling back.")
                time.sleep(1.0)
        raise RuntimeError("unreachable: both attempts exhausted without raising")

    # ---------- internals ----------

    def _call(self, model, messages, json_mode, temperature, max_tokens):
        kwargs: dict[str, Any] = dict(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if json_mode:
            # OpenRouter forwards response_format to providers that support it
            # (Gemini, OpenAI). For models that don't, the system prompt's
            # explicit "RETURN ONLY JSON" instruction does the work.
            kwargs["response_format"] = {"type": "json_object"}
        return self.client.chat.completions.create(**kwargs)

    @staticmethod
    def _build_messages(
        system: str, user: str, image_path: str | None, image_url: str | None
    ) -> list[dict[str, Any]]:
        user_content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        if image_path:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _b64_data_url(Path(image_path))},
                }
            )
        elif image_url:
            user_content.append({"type": "image_url", "image_url": {"url": image_url}})

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]


def _b64_data_url(path: Path) -> str:
    """Local image -> data URL the model can consume."""
    suffix = path.suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(
        suffix, "jpeg"
    )
    return f"data:image/{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def parse_json_strict(text: str) -> dict:
    """Parse the model's JSON output, stripping any markdown fences."""
    t = text.strip()
    if t.startswith("```"):
        # Strip a ```json ... ``` fence the model occasionally emits despite
        # being told not to.
        t = t.strip("`")
        if t.startswith("json"):
            t = t[4:]
        t = t.strip()
    return json.loads(t)
