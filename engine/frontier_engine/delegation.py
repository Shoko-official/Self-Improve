"""Bounded, auditable specialist delegation planning."""

from __future__ import annotations

from dataclasses import dataclass


SPECIALISTS = {
    "research": "literature and evidence analysis",
    "engineering": "code and test analysis",
    "reviewer": "claim and provenance review",
    "data": "tabular and statistical analysis",
}
MAX_TASKS = 8


@dataclass(frozen=True)
class DelegationTask:
    specialist: str
    objective: str
    side_effects: bool = False


@dataclass(frozen=True)
class DelegationPlan:
    project_id: str
    tasks: tuple[DelegationTask, ...]
    approved: bool
    evidence: tuple[str, ...]


def build_delegation_plan(project_id: str, tasks: tuple[DelegationTask, ...], *, approved: bool = False) -> DelegationPlan:
    if not project_id.strip():
        raise ValueError("FR-DELEGATION-PROJECT: project_id is required")
    if not tasks or len(tasks) > MAX_TASKS:
        raise ValueError("FR-DELEGATION-BOUND: task count must be between one and eight")
    seen: set[str] = set()
    evidence: list[str] = []
    for task in tasks:
        if task.specialist not in SPECIALISTS:
            raise ValueError("FR-DELEGATION-SPECIALIST: specialist is not allowlisted")
        if task.specialist in seen:
            raise ValueError("FR-DELEGATION-DUPLICATE: specialist may appear once per plan")
        if not task.objective.strip():
            raise ValueError("FR-DELEGATION-OBJECTIVE: objective is required")
        seen.add(task.specialist)
        evidence.append(f"{task.specialist}:{SPECIALISTS[task.specialist]}")
        if task.side_effects and not approved:
            raise PermissionError("FR-DELEGATION-APPROVAL: side effects require explicit approval")
    return DelegationPlan(project_id, tasks, approved, tuple(evidence))
