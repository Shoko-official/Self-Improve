"""Safe compute planning and real local command execution."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Literal

ComputeTarget = Literal["local", "ssh", "slurm", "cloud"]

@dataclass(frozen=True)
class ComputePlan:
 target: ComputeTarget; script: tuple[str,...]; cpu: int; memory_mb: int; timeout_seconds: int; estimated_cost_usd: float; egress_bytes: int

class ComputeApprovalRequired(PermissionError): pass

def validate_plan(plan: ComputePlan, approved: bool) -> None:
 if not plan.script: raise ValueError("FR-REMOTE-SCRIPT: exact command required")
 if plan.cpu < 1 or plan.memory_mb < 1 or plan.timeout_seconds < 1: raise ValueError("FR-REMOTE-RESOURCES: positive resource limits required")
 if plan.estimated_cost_usd < 0 or plan.egress_bytes < 0: raise ValueError("FR-REMOTE-PREVIEW: costs and egress cannot be negative")
 if plan.target != "local" and not approved: raise ComputeApprovalRequired("FR-REMOTE-APPROVAL: remote plan requires explicit approval")

def run_local(plan: ComputePlan) -> dict[str, object]:
 validate_plan(plan, approved=True)
 if plan.target != "local": raise ValueError("FR-REMOTE-TARGET: run_local only accepts local plans")
 try:
  completed=subprocess.run(plan.script,capture_output=True,text=True,timeout=plan.timeout_seconds,check=False)
 except subprocess.TimeoutExpired as error:
  return {"state":"failed","diagnostic":{"code":"FR-REMOTE-TIMEOUT","evidence":str(error)}}
 return {"state":"succeeded" if completed.returncode == 0 else "failed","exit_code":completed.returncode,"stdout":completed.stdout,"stderr":completed.stderr}
