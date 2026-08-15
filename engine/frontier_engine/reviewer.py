"""Evidence-gap reviewer. It inspects records and never claims to rerun work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ClaimKind = Literal["source", "computed", "inference", "hypothesis"]


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    kind: ClaimKind
    citation_ids: tuple[str, ...] = ()
    execution_log_id: str | None = None


@dataclass(frozen=True)
class ReviewFinding:
    claim_id: str
    code: str
    severity: Literal["warning", "error"]
    message: str
    evidence_ids: tuple[str, ...]


def review_claims(claims: tuple[Claim, ...]) -> tuple[ReviewFinding, ...]:
    findings: list[ReviewFinding] = []
    for claim in claims:
        if claim.kind == "source" and not claim.citation_ids:
            findings.append(ReviewFinding(claim.id, "FR-REVIEW-UNSOURCED", "error", "Source-backed claim has no exact citation.", ()))
        if claim.kind == "computed" and not claim.execution_log_id:
            findings.append(ReviewFinding(claim.id, "FR-REVIEW-UNTRACEABLE-COMPUTATION", "error", "Computed claim has no execution-log record.", claim.citation_ids))
        if claim.kind == "inference" and not claim.citation_ids and not claim.execution_log_id:
            findings.append(ReviewFinding(claim.id, "FR-REVIEW-UNSUPPORTED-INFERENCE", "warning", "Inference has neither cited source nor execution evidence.", ()))
    return tuple(findings)
