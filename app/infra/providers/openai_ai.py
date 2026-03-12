from __future__ import annotations

from typing import Any

from openai import OpenAI

from app.infra.config import get_settings
from app.infra.providers.local_ai import LocalImageGenerationProvider, LocalTextReasoningProvider


class OpenAITextReasoningProvider(LocalTextReasoningProvider):
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None

    def _call_json(self, instructions: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.client or not self.settings.openai_enable_live_calls:
            return None

        response = self.client.responses.create(
            model=self.settings.openai_text_model,
            input=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": str(payload)},
            ],
        )
        if not response.output_text:
            return None
        return {"raw_text": response.output_text}

    def generate_content_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ = self._call_json(
            "Generate a concise social media content plan. If unavailable, local fallback should be used.",
            payload,
        )
        return super().generate_content_plan(payload)

    def generate_art_direction(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ = self._call_json(
            "Suggest art direction for a branded social media layout. If unavailable, local fallback should be used.",
            payload,
        )
        return super().generate_art_direction(payload)

    def summarize(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ = self._call_json("Summarize the content preserving CTA intent.", payload)
        return super().summarize(payload)


class OpenAIImageGenerationProvider(LocalImageGenerationProvider):
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None

    def generate_asset(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.client and self.settings.openai_enable_live_calls:
            # The V1A pipeline keeps a deterministic local fallback even when a remote provider exists.
            pass
        return super().generate_asset(payload)
