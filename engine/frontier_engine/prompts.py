"""Original, bounded prompt variants for Frontier agent sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PromptVariant = Literal["compact", "standard", "extended"]


@dataclass(frozen=True)
class PromptPack:
    variant: PromptVariant
    token_budget: int
    content: str
    estimated_tokens: int


_BUDGETS: dict[PromptVariant, int] = {"compact": 180, "standard": 450, "extended": 900}
_CORE = """You are Frontier, a local-first workbench agent. Ground claims in inspected files, execution logs, and cited sources. State uncertainty plainly. Keep data local unless the user approves a named external recipient and payload."""
_STANDARD = """Before acting, form a brief plan and keep todos current. Use only granted tools and project folders. Preserve user changes. Record outputs with model, runtime, parameters, inputs, and parent artifacts. Treat cancellation, permission denial, and failed diagnostics as real states."""
_EXTENDED = """For scientific work, keep claims, observations, computations, inferences, and hypotheses distinct. An execution log is authoritative for what ran. Reviewer findings can identify evidence gaps but cannot claim to rerun an analysis. Cite exact source regions when making source-backed claims. Do not represent a fixture, unavailable adapter, or unsupported modality as working. Request approval before external writes, paid compute, remote data transfer, destructive work, or a consequential scientific action."""


def compile_prompt(variant: PromptVariant, project_instructions: str = "", tools: tuple[str, ...] = ()) -> PromptPack:
    sections = [_CORE]
    if variant in {"standard", "extended"}:
        sections.append(_STANDARD)
    if variant == "extended":
        sections.append(_EXTENDED)
    if project_instructions.strip():
        sections.append(f"Project instructions: {project_instructions.strip()}")
    if tools:
        sections.append("Granted tools: " + ", ".join(sorted(set(tools))) + ".")
    content = "\n\n".join(sections)
    estimated_tokens = _estimate_tokens(content)
    budget = _BUDGETS[variant]
    if estimated_tokens > budget:
        raise ValueError(f"{variant} prompt exceeds its {budget}-token budget.")
    return PromptPack(variant, budget, content, estimated_tokens)


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)
