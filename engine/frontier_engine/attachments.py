"""Bounded local multimodal attachment inspection and explicit adaptations."""

from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import Path


MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024
_THREED = {"model/obj", "model/gltf+json", "model/gltf-binary", "application/ply"}


@dataclass(frozen=True)
class AttachmentDescriptor:
    name: str
    path: str
    media_type: str
    kind: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class AdaptationPlan:
    source_media_type: str
    target: str
    mode: str
    disclosure: str


def inspect_attachment(path: Path, max_bytes: int = MAX_ATTACHMENT_BYTES) -> AttachmentDescriptor:
    if max_bytes <= 0:
        raise ValueError("FR-ATTACHMENT-LIMIT: max_bytes must be positive")
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError("FR-ATTACHMENT-NOT-FOUND")
    size = resolved.stat().st_size
    if size > max_bytes:
        raise ValueError("FR-ATTACHMENT-TOO-LARGE")
    data = resolved.read_bytes()
    media_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
    if media_type in _THREED:
        kind = "3d"
    elif media_type.startswith("image/"):
        kind = "image"
    elif media_type.startswith("video/"):
        kind = "video"
    elif media_type.startswith("audio/"):
        kind = "audio"
    elif media_type.startswith("text/") or media_type in {"application/pdf", "application/json"}:
        kind = "document"
    else:
        kind = "binary"
    return AttachmentDescriptor(resolved.name, str(resolved), media_type, kind, len(data), hashlib.sha256(data).hexdigest())


def plan_adaptation(media_type: str, target: str) -> AdaptationPlan:
    if not media_type or not target:
        raise ValueError("FR-ATTACHMENT-ADAPTATION: media type and target are required")
    if media_type in _THREED and target in {"vision", "image"}:
        return AdaptationPlan(media_type, target, "derived_multiview", "3D was converted to derived multiview images; the target did not receive native 3D.")
    if (media_type.startswith("image/") and target == "vision") or (media_type.startswith("audio/") and target == "audio") or (media_type.startswith("video/") and target == "video"):
        return AdaptationPlan(media_type, target, "native", "Native modality retained.")
    raise ValueError("FR-ATTACHMENT-ADAPTATION-UNSUPPORTED")
