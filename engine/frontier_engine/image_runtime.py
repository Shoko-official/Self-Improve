"""Loopback-only ComfyUI contract for local image generation."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class ImageRuntimeError(RuntimeError):
    pass


class ComfyUIAdapter:
    """Small, inspectable adapter for a user-operated local ComfyUI server."""

    def __init__(self, base_url: str) -> None:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("FR-IMAGE-COMFYUI-LOOPBACK")
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict[str, object]:
        stats = self._request("GET", "system_stats")
        object_info = self._request("GET", "object_info")
        if not isinstance(object_info, dict):
            raise ImageRuntimeError("FR-IMAGE-COMFYUI-OBJECT-INFO")
        return {
            "runtime": "ComfyUI",
            "healthy": True,
            "endpoint": self.base_url,
            "nodes": sorted(str(name) for name in object_info),
            "system": stats,
        }

    def submit(self, workflow: dict[str, object], *, approved: bool) -> dict[str, object]:
        if not approved:
            raise PermissionError("FR-IMAGE-COMFYUI-APPROVAL")
        if not workflow:
            raise ValueError("FR-IMAGE-COMFYUI-WORKFLOW")
        response = self._request("POST", "prompt", {"prompt": workflow})
        prompt_id = response.get("prompt_id") if isinstance(response, dict) else None
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ImageRuntimeError("FR-IMAGE-COMFYUI-PROMPT-ID")
        return {"runtime": "ComfyUI", "prompt_id": prompt_id, "state": "queued"}

    def history(self, prompt_id: str) -> dict[str, object]:
        if not prompt_id:
            raise ValueError("FR-IMAGE-COMFYUI-PROMPT-ID")
        response = self._request("GET", f"history/{urllib.parse.quote(prompt_id, safe='')}")
        record = response.get(prompt_id) if isinstance(response, dict) else None
        if record is None:
            return {"runtime": "ComfyUI", "prompt_id": prompt_id, "state": "pending", "outputs": []}
        outputs = record.get("outputs", {}) if isinstance(record, dict) else {}
        files = []
        if isinstance(outputs, dict):
            for node_id, output in outputs.items():
                for image in output.get("images", []) if isinstance(output, dict) else []:
                    if isinstance(image, dict) and isinstance(image.get("filename"), str):
                        files.append({"node_id": str(node_id), "filename": image["filename"], "subfolder": str(image.get("subfolder", "")), "type": str(image.get("type", "output"))})
        return {"runtime": "ComfyUI", "prompt_id": prompt_id, "state": "completed" if files else "running", "outputs": files}

    def _request(self, method: str, path: str, payload: dict[str, object] | None = None) -> Any:
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(f"{self.base_url}/{path.lstrip('/')}", data=body, method=method, headers={"Content-Type": "application/json"} if body else {})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as error:
            raise ImageRuntimeError(f"FR-IMAGE-COMFYUI-REQUEST: {error}") from error
