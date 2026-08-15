"""Deterministic local policy evaluation without secret-bearing policy data."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


_SECRET = re.compile(r"(api[_-]?key|token|password|secret|private[_-]?key|credential)", re.IGNORECASE)
_PRECEDENCE = ("immutable", "organization", "command_line", "environment", "user", "application", "default")


@dataclass(frozen=True)
class OrganizationPolicy:
    organization_id: str
    name: str
    values: Mapping[str, Any]


@dataclass(frozen=True)
class DeviceRecord:
    device_id: str
    platform: str
    machine: str
    organization_id: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    key: str
    value: Any
    source: str
    evidence: tuple[str, ...]


class PolicyError(ValueError):
    pass


def _reject_secrets(value: Any, path: str = "policy") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if _SECRET.search(key_text):
                raise PolicyError("FR-POLICY-SECRET: policy files cannot contain secrets")
            _reject_secrets(child, f"{path}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_secrets(child, f"{path}[{index}]")


def evaluate_policy(key: str, layers: Mapping[str, Mapping[str, Any]]) -> PolicyDecision:
    """Select the first defined value in the documented policy precedence."""
    key = key.strip()
    if not key:
        raise PolicyError("FR-POLICY-KEY: policy key is required")
    for layer in _PRECEDENCE:
        values = layers.get(layer, {})
        _reject_secrets(values, layer)
        if key in values:
            return PolicyDecision(key, values[key], layer, tuple(f"{name}:{key}" for name in _PRECEDENCE if key in layers.get(name, {})))
    return PolicyDecision(key, None, "absent", ())


def validate_policy_layers(layers: Mapping[str, Mapping[str, Any]]) -> dict[str, object]:
    unknown = sorted(set(layers) - set(_PRECEDENCE))
    if unknown:
        raise PolicyError(f"FR-POLICY-LAYER: unsupported layers: {', '.join(unknown)}")
    for name, values in layers.items():
        if not isinstance(values, Mapping):
            raise PolicyError(f"FR-POLICY-SCHEMA: layer {name} must be an object")
        _reject_secrets(values, name)
    return {"valid": True, "precedence": list(_PRECEDENCE), "layers": sorted(layers)}
