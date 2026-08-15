"""Local scientific connector and skill descriptors with explicit trust boundaries."""

from __future__ import annotations

CONNECTORS = (
    {"id": "local-literature", "capabilities": ["literature.query", "literature.evidence"], "network": "none", "availability": "local-ledger"},
    {"id": "local-artifacts", "capabilities": ["artifact.read", "artifact.version"], "network": "none", "availability": "local-ledger"},
    {"id": "huggingface-model-catalog", "capabilities": ["model.search", "model.file-transfer"], "network": "explicit-egress", "availability": "opt-in"},
)

SKILLS = (
    {"id": "evidence-review", "capabilities": ["claim.review", "evidence.gap"], "network": "none", "availability": "local-engine"},
    {"id": "artifact-provenance", "capabilities": ["artifact.lineage", "artifact.annotation"], "network": "none", "availability": "local-engine"},
    {"id": "reproducible-kernel", "capabilities": ["kernel.python", "kernel.r", "environment.fingerprint"], "network": "none", "availability": "local-engine"},
)


def connector_catalog() -> list[dict[str, object]]: return [dict(item) for item in CONNECTORS]


def skill_catalog() -> list[dict[str, object]]: return [dict(item) for item in SKILLS]
