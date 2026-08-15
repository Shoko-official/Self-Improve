"""Explicit remote-provider contracts with no automatic egress or fallback."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str | None = None
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class EgressPreview:
    provider: str
    endpoint: str
    text_bytes: int
    attachment_names: tuple[str, ...]
    attachment_bytes: int


class ProviderError(RuntimeError):
    pass


class EgressApprovalRequired(PermissionError):
    pass


class OpenAICompatibleProvider:
    """OpenAI Chat Completions protocol adapter for a user-configured endpoint."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def preview_egress(self, messages: Sequence[dict[str, str]], attachments: Sequence[tuple[str, int]] = ()) -> EgressPreview:
        return EgressPreview(
            provider=self.config.name,
            endpoint=self._url("chat/completions"),
            text_bytes=sum(len(message.get("content", "").encode()) for message in messages),
            attachment_names=tuple(name for name, _ in attachments),
            attachment_bytes=sum(size for _, size in attachments),
        )

    def health(self) -> dict[str, Any]:
        response = self._request("GET", "models")
        models = response.get("data")
        if not isinstance(models, list):
            raise ProviderError("FR-PROVIDER-MODELS: endpoint returned no model list")
        return {"provider": self.config.name, "healthy": True, "models": [model.get("id") for model in models if isinstance(model, dict)]}

    def stream_chat(
        self,
        model: str,
        messages: Sequence[dict[str, str]],
        *,
        egress_approved: bool,
        attachments: Sequence[tuple[str, int]] = (),
    ) -> Iterator[str]:
        if not egress_approved:
            preview = self.preview_egress(messages, attachments)
            raise EgressApprovalRequired(f"FR-PROVIDER-EGRESS: approval required for {preview.provider} at {preview.endpoint}")
        payload = json.dumps({"model": model, "messages": list(messages), "stream": True}).encode()
        request = urllib.request.Request(self._url("chat/completions"), data=payload, method="POST", headers=self._headers({"Content-Type": "application/json", "Accept": "text/event-stream"}))
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                for raw_line in response:
                    line = raw_line.decode().strip()
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        return
                    event = json.loads(data)
                    choices = event.get("choices", [])
                    if choices and isinstance(choices[0], dict):
                        delta = choices[0].get("delta", {})
                        if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                            yield delta["content"]
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as error:
            raise ProviderError(f"FR-PROVIDER-STREAM: {error}") from error

    def _request(self, method: str, path: str) -> dict[str, Any]:
        request = urllib.request.Request(self._url(path), method=method, headers=self._headers())
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as error:
            raise ProviderError(f"FR-PROVIDER-HEALTH: {error}") from error
        if not isinstance(payload, dict):
            raise ProviderError("FR-PROVIDER-HEALTH: endpoint returned a non-object response")
        return payload

    def _headers(self, values: dict[str, str] | None = None) -> dict[str, str]:
        headers = dict(values or {})
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}/v1/{path.lstrip('/')}"


class NvidiaNimProvider(OpenAICompatibleProvider):
    """NVIDIA NIM preset using its OpenAI-compatible inference surface."""

    def __init__(self, base_url: str, api_key: str | None = None, timeout_seconds: float = 30.0) -> None:
        super().__init__(ProviderConfig("NVIDIA NIM", base_url, api_key, timeout_seconds))
