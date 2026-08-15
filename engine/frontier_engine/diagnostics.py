"""Stable, evidence-based diagnostics without leaking sensitive values."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
Severity=Literal["info","warning","error"]
@dataclass(frozen=True)
class Inference: statement:str; confidence:float
@dataclass(frozen=True)
class Diagnostic:
 code:str; severity:Severity; component:str; summary:str; facts:tuple[str,...]; inferences:tuple[Inference,...]; evidence_ids:tuple[str,...]; remediation:tuple[str,...]; redacted_fields:tuple[str,...]=()
def validate(diagnostic:Diagnostic)->None:
 if not diagnostic.code.startswith("FR-"):raise ValueError("Diagnostic codes must use the FR- prefix")
 if not diagnostic.facts:raise ValueError("A diagnostic needs observed facts")
 if not diagnostic.evidence_ids:raise ValueError("A diagnostic needs evidence references")
 if any(not 0<=item.confidence<=1 for item in diagnostic.inferences):raise ValueError("Inference confidence must be within 0..1")
def user_view(diagnostic:Diagnostic,details:dict[str,str])->dict[str,object]:
 validate(diagnostic);return {"code":diagnostic.code,"severity":diagnostic.severity,"summary":diagnostic.summary,"facts":diagnostic.facts,"inferences":[{"statement":x.statement,"confidence":x.confidence}for x in diagnostic.inferences],"evidence_ids":diagnostic.evidence_ids,"remediation":diagnostic.remediation,"details":{key:("[redacted]" if key in diagnostic.redacted_fields else value)for key,value in details.items()}}
