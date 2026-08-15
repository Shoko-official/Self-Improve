"""Execution-time credential handles with redacted diagnostics."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping


_HANDLE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_ENV = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


@dataclass(frozen=True)
class CredentialHandle:
    name: str
    environment_variable: str

    def __post_init__(self) -> None:
        if not _HANDLE.fullmatch(self.name): raise ValueError("FR-CREDENTIAL-HANDLE: invalid handle name")
        if not _ENV.fullmatch(self.environment_variable): raise ValueError("FR-CREDENTIAL-ENV: invalid environment variable")


@dataclass(frozen=True)
class CredentialStatus:
    name: str
    environment_variable: str
    available: bool


def inspect_credential(handle: CredentialHandle, environ: Mapping[str, str] | None = None) -> CredentialStatus:
    values = environ if environ is not None else os.environ
    return CredentialStatus(handle.name, handle.environment_variable, bool(values.get(handle.environment_variable, "")))


def resolve_credential(handle: CredentialHandle, environ: Mapping[str, str] | None = None) -> str:
    values = environ if environ is not None else os.environ
    value = values.get(handle.environment_variable, "")
    if not value: raise PermissionError("FR-CREDENTIAL-MISSING: named credential is unavailable")
    return value
