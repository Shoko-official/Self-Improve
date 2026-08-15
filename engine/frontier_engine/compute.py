"""Safe compute planning and real local command execution."""

from __future__ import annotations

import subprocess
import shlex
from dataclasses import dataclass
from typing import Literal

ComputeTarget = Literal["local", "ssh", "slurm", "cloud"]

@dataclass(frozen=True)
class ComputePlan:
 target: ComputeTarget; script: tuple[str,...]; cpu: int; memory_mb: int; timeout_seconds: int; estimated_cost_usd: float; egress_bytes: int; endpoint: str|None=None; working_directory: str|None=None

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

def run_remote(plan: ComputePlan, approved: bool) -> dict[str, object]:
 validate_plan(plan, approved)
 if plan.target == "cloud": return {"state":"failed","diagnostic":{"code":"FR-REMOTE-CLOUD-NOT-CONFIGURED"}}
 if not plan.endpoint or any(character.isspace() for character in plan.endpoint): raise ValueError("FR-REMOTE-ENDPOINT: exact endpoint required")
 if plan.working_directory and not plan.working_directory.startswith("/"): raise ValueError("FR-REMOTE-WORKDIR: absolute POSIX path required")
 if plan.target == "ssh":
  command=["ssh",plan.endpoint,"--",*plan.script]
 else:
  wrapped=shlex.join(plan.script); command=["sbatch","--parsable","--cpus-per-task",str(plan.cpu),"--mem",f"{plan.memory_mb}M","--time",str(plan.timeout_seconds),"--wrap",wrapped]
  if plan.working_directory: command.extend(["--chdir",plan.working_directory])
 try:
  completed=subprocess.run(command,capture_output=True,text=True,timeout=plan.timeout_seconds,check=False)
 except FileNotFoundError as error:
  return {"state":"failed","diagnostic":{"code":"FR-REMOTE-EXECUTOR-NOT-FOUND","evidence":str(error)}}
 except subprocess.TimeoutExpired as error:
  return {"state":"failed","diagnostic":{"code":"FR-REMOTE-TIMEOUT","evidence":str(error)}}
 result={"state":"succeeded" if completed.returncode == 0 else "failed","exit_code":completed.returncode,"stdout":completed.stdout,"stderr":completed.stderr,"command":command}
 if plan.target == "slurm" and completed.returncode == 0: result["scheduler_job_id"]=completed.stdout.strip()
 if completed.returncode != 0: result["diagnostic"]={"code":"FR-REMOTE-EXECUTION-FAILED"}
 return result
