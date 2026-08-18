"""Durable, capability-gated local AI pipelines."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from frontier_engine.claims import ClaimLedger
from frontier_engine.inference import plan_ollama_inference
from frontier_engine.kernels import PythonKernel
from frontier_engine.literature import LiteratureStore
from frontier_engine.model_registry import HuggingFaceHub
from frontier_engine.reviewer import Claim, review_claims
from frontier_engine.runtimes import stream_ollama
from frontier_engine.store import FrontierStore


PIPELINE_STEP_KINDS = {"model", "skill", "connector"}
SKILL_EXECUTORS = {"evidence-review", "artifact-provenance", "reproducible-kernel"}
CONNECTOR_EXECUTORS = {"local-literature": False, "local-artifacts": False, "huggingface-model-catalog": True}
_STEP_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class AutomationRun:
    automation_id: str
    mode: str
    state: str
    external_effects: bool


def pipeline_capabilities() -> dict[str, object]:
    return {
        "step_types": [{"id": kind} for kind in sorted(PIPELINE_STEP_KINDS)],
        "skills": [{"id": identifier, "external_effects": False} for identifier in sorted(SKILL_EXECUTORS)],
        "connectors": [{"id": identifier, "external_effects": external} for identifier, external in CONNECTOR_EXECUTORS.items()],
        "schedules": [{"id": "manual"}, {"id": "interval", "minimum_seconds": 60}],
    }


class AutomationStore:
    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self) -> None:
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS automations (id TEXT PRIMARY KEY,name TEXT NOT NULL,definition TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS automation_runs (id TEXT PRIMARY KEY,automation_id TEXT NOT NULL,mode TEXT NOT NULL,state TEXT NOT NULL,external_effects INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS automation_steps (
                id TEXT PRIMARY KEY,automation_id TEXT NOT NULL REFERENCES automations(id),step_key TEXT NOT NULL,kind TEXT NOT NULL,
                config_json TEXT NOT NULL,dependencies_json TEXT NOT NULL,max_retries INTEGER NOT NULL,external_effects INTEGER NOT NULL,position INTEGER NOT NULL,
                UNIQUE(automation_id,step_key)
            );
            CREATE TABLE IF NOT EXISTS automation_step_runs (
                id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES automation_runs(id),step_key TEXT NOT NULL,attempt INTEGER NOT NULL,state TEXT NOT NULL,
                input_json TEXT NOT NULL,output_json TEXT,diagnostic_json TEXT,started_at TEXT NOT NULL,completed_at TEXT,
                UNIQUE(run_id,step_key,attempt)
            );
        """)
        self._add_columns("automations", {
            "project_id": "TEXT NOT NULL DEFAULT ''", "schedule_json": "TEXT NOT NULL DEFAULT '{\"kind\":\"manual\"}'",
            "enabled": "INTEGER NOT NULL DEFAULT 1", "next_due_at": "TEXT", "created_at": "TEXT NOT NULL DEFAULT ''", "updated_at": "TEXT NOT NULL DEFAULT ''",
        })
        self._add_columns("automation_runs", {
            "trigger_kind": "TEXT NOT NULL DEFAULT 'manual'", "external_approved": "INTEGER NOT NULL DEFAULT 0", "parent_run_id": "TEXT",
            "diagnostic_json": "TEXT", "created_at": "TEXT NOT NULL DEFAULT ''", "started_at": "TEXT", "completed_at": "TEXT",
        })
        self.connection.commit()

    def _add_columns(self, table: str, definitions: Mapping[str, str]) -> None:
        existing = {str(row["name"]) for row in self.connection.execute(f"PRAGMA table_info({table})")}
        for name, definition in definitions.items():
            if name not in existing:
                self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def close(self) -> None:
        self.connection.close()

    def create(self, name: str, definition: str) -> str:
        identifier = str(uuid.uuid4())
        now = _now()
        self.connection.execute(
            "INSERT INTO automations(id,name,definition,project_id,schedule_json,enabled,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?)",
            (identifier, name, definition, "", _json({"kind": "manual"}), now, now),
        )
        self.connection.commit()
        return identifier

    def create_pipeline(self, project_id: str, name: str, steps: list[dict[str, object]], schedule: Mapping[str, object] | None = None) -> dict[str, object]:
        name = name.strip()
        project_id = project_id.strip()
        if not name or not project_id:
            raise ValueError("Pipeline project and name are required.")
        normalized_steps = _validate_steps(steps, project_id)
        normalized_schedule, next_due = _validate_schedule(schedule or {"kind": "manual"})
        identifier = str(uuid.uuid4())
        now = _now()
        self.connection.execute(
            "INSERT INTO automations(id,name,definition,project_id,schedule_json,enabled,next_due_at,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?,?)",
            (identifier, name, _json({"version": 1}), project_id, _json(normalized_schedule), next_due, now, now),
        )
        for position, step in enumerate(normalized_steps):
            self.connection.execute(
                "INSERT INTO automation_steps VALUES(?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), identifier, step["key"], step["kind"], _json(step["config"]), _json(step["depends_on"]), step["max_retries"], int(step["external_effects"]), position),
            )
        self.connection.commit()
        return self.pipeline(identifier)

    def pipelines(self, project_id: str | None = None) -> list[dict[str, object]]:
        where = "WHERE project_id = ?" if project_id else ""
        parameters: tuple[str, ...] = (project_id,) if project_id else ()
        return [self.pipeline(str(row["id"])) for row in self.connection.execute(f"SELECT id FROM automations {where} ORDER BY created_at DESC,id DESC", parameters)]

    def pipeline(self, automation_id: str) -> dict[str, object]:
        row = self.connection.execute("SELECT * FROM automations WHERE id=?", (automation_id,)).fetchone()
        if row is None:
            raise KeyError("Automation not found")
        steps = [{
            "key": step["step_key"], "kind": step["kind"], "config": json.loads(step["config_json"]), "depends_on": json.loads(step["dependencies_json"]),
            "max_retries": step["max_retries"], "external_effects": bool(step["external_effects"]),
        } for step in self.connection.execute("SELECT * FROM automation_steps WHERE automation_id=? ORDER BY position", (automation_id,))]
        return {
            "id": row["id"], "project_id": row["project_id"], "name": row["name"], "schedule": json.loads(row["schedule_json"]),
            "enabled": bool(row["enabled"]), "next_due_at": row["next_due_at"], "created_at": row["created_at"], "updated_at": row["updated_at"],
            "steps": steps, "external_effects": any(bool(step["external_effects"]) for step in steps) or "external" in str(row["definition"]),
        }

    def queue_run(self, automation_id: str, dry_run: bool = True, external_approved: bool = False, trigger_kind: str = "manual", parent_run_id: str | None = None) -> dict[str, object]:
        pipeline = self.pipeline(automation_id)
        if pipeline["external_effects"] and not dry_run and not external_approved:
            raise PermissionError("FR-AUTO-APPROVAL: external effects require explicit approval")
        run_id = str(uuid.uuid4())
        state = "simulated" if dry_run else "queued"
        mode = "dry_run" if dry_run else "execute"
        completed_at = _now() if dry_run else None
        self.connection.execute(
            "INSERT INTO automation_runs(id,automation_id,mode,state,external_effects,trigger_kind,external_approved,parent_run_id,created_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (run_id, automation_id, mode, state, int(pipeline["external_effects"]), trigger_kind, int(external_approved), parent_run_id, _now(), completed_at),
        )
        if dry_run:
            for step in pipeline["steps"]:
                self._record_step(run_id, step, 0, "simulated", {"dependencies": step["depends_on"]}, {"validated": True})
        if not dry_run and trigger_kind == "manual":
            self._advance_schedule(automation_id)
        self.connection.commit()
        return self.run_record(run_id)

    def queue_due_run(self, automation_id: str, at: str | None = None) -> dict[str, object] | None:
        pipeline = self.pipeline(automation_id)
        if pipeline["external_effects"]:
            raise PermissionError("FR-AUTO-APPROVAL: scheduled external effects require an approved manual run")
        schedule = pipeline["schedule"]
        if schedule["kind"] != "interval":
            return None
        due_at = at or _now()
        base = datetime.fromisoformat(due_at)
        next_due = (base + timedelta(seconds=int(schedule["interval_seconds"]))).isoformat()
        changed = self.connection.execute(
            "UPDATE automations SET next_due_at=?,updated_at=? WHERE id=? AND enabled=1 AND next_due_at IS NOT NULL AND next_due_at<=?",
            (next_due, _now(), automation_id, due_at),
        )
        if changed.rowcount != 1:
            self.connection.commit()
            return None
        run_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO automation_runs(id,automation_id,mode,state,external_effects,trigger_kind,external_approved,parent_run_id,created_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (run_id, automation_id, "execute", "queued", 0, "schedule", 0, None, _now(), None),
        )
        self.connection.commit()
        return self.run_record(run_id)

    def run(self, automation_id: str, dry_run: bool = True, external_approved: bool = False) -> AutomationRun:
        record = self.queue_run(automation_id, dry_run, external_approved)
        if not dry_run:
            self._set_run_state(str(record["id"]), "completed", completed_at=_now())
            record = self.run_record(str(record["id"]))
        return AutomationRun(automation_id, str(record["mode"]), str(record["state"]), bool(record["external_effects"]))

    def history(self, automation_id: str) -> tuple[AutomationRun, ...]:
        return tuple(AutomationRun(str(row["automation_id"]), str(row["mode"]), str(row["state"]), bool(row["external_effects"])) for row in self.connection.execute("SELECT * FROM automation_runs WHERE automation_id=? ORDER BY created_at,id", (automation_id,)))

    def run_records(self, automation_id: str | None = None) -> list[dict[str, object]]:
        where = "WHERE automation_id=?" if automation_id else ""
        parameters: tuple[str, ...] = (automation_id,) if automation_id else ()
        return [self.run_record(str(row["id"])) for row in self.connection.execute(f"SELECT id FROM automation_runs {where} ORDER BY created_at DESC,id DESC", parameters)]

    def run_record(self, run_id: str) -> dict[str, object]:
        row = self.connection.execute("SELECT * FROM automation_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError("Automation run not found")
        steps = [{
            "id": step["id"], "step_key": step["step_key"], "attempt": step["attempt"], "state": step["state"], "input": json.loads(step["input_json"]),
            "output": json.loads(step["output_json"]) if step["output_json"] else None, "diagnostic": json.loads(step["diagnostic_json"]) if step["diagnostic_json"] else None,
            "started_at": step["started_at"], "completed_at": step["completed_at"],
        } for step in self.connection.execute("SELECT * FROM automation_step_runs WHERE run_id=? ORDER BY started_at,id", (run_id,))]
        return {
            "id": row["id"], "automation_id": row["automation_id"], "mode": row["mode"], "state": row["state"], "external_effects": bool(row["external_effects"]),
            "external_approved": bool(row["external_approved"]), "trigger_kind": row["trigger_kind"], "parent_run_id": row["parent_run_id"],
            "diagnostic": json.loads(row["diagnostic_json"]) if row["diagnostic_json"] else None, "created_at": row["created_at"],
            "started_at": row["started_at"], "completed_at": row["completed_at"], "steps": steps,
        }

    def claim_run(self, run_id: str) -> dict[str, object]:
        changed = self.connection.execute("UPDATE automation_runs SET state='running',started_at=? WHERE id=? AND state='queued'", (_now(), run_id))
        if changed.rowcount != 1:
            raise ValueError("Automation run cannot be claimed unless queued.")
        self.connection.commit()
        return self.run_record(run_id)

    def request_cancellation(self, run_id: str) -> dict[str, object]:
        record = self.run_record(run_id)
        if record["state"] == "queued":
            self._set_run_state(run_id, "cancelled", completed_at=_now())
        elif record["state"] == "running":
            self._set_run_state(run_id, "cancel_requested")
        else:
            raise ValueError(f"Automation run cannot be cancelled from state: {record['state']}")
        return self.run_record(run_id)

    def retry_run(self, run_id: str, external_approved: bool = False) -> dict[str, object]:
        record = self.run_record(run_id)
        if record["state"] not in {"failed", "cancelled"}:
            raise ValueError("Only failed or cancelled automation runs can be retried.")
        return self.queue_run(str(record["automation_id"]), False, external_approved, "retry", run_id)

    def complete_run(self, run_id: str, state: str = "succeeded", diagnostic: Mapping[str, object] | None = None) -> dict[str, object]:
        current = self.run_record(run_id)
        if current["state"] == "cancel_requested":
            state = "cancelled"
        if current["state"] not in {"running", "cancel_requested"}:
            raise ValueError("Automation run is not active.")
        self._set_run_state(run_id, state, diagnostic, _now())
        return self.run_record(run_id)

    def _set_run_state(self, run_id: str, state: str, diagnostic: Mapping[str, object] | None = None, completed_at: str | None = None) -> None:
        self.connection.execute("UPDATE automation_runs SET state=?,diagnostic_json=?,completed_at=? WHERE id=?", (state, _json(diagnostic) if diagnostic else None, completed_at, run_id))
        self.connection.commit()

    def _record_step(self, run_id: str, step: Mapping[str, object], attempt: int, state: str, inputs: Mapping[str, object], output: Mapping[str, object] | None = None, diagnostic: Mapping[str, object] | None = None) -> str:
        identifier = str(uuid.uuid4())
        completed_at = None if state == "running" else _now()
        self.connection.execute("INSERT INTO automation_step_runs VALUES(?,?,?,?,?,?,?,?,?,?)", (identifier, run_id, step["key"], attempt, state, _json(inputs), _json(output) if output is not None else None, _json(diagnostic) if diagnostic else None, _now(), completed_at))
        self.connection.commit()
        return identifier

    def finish_step(self, step_run_id: str, state: str, output: Mapping[str, object] | None = None, diagnostic: Mapping[str, object] | None = None) -> None:
        self.connection.execute("UPDATE automation_step_runs SET state=?,output_json=?,diagnostic_json=?,completed_at=? WHERE id=?", (state, _json(output) if output is not None else None, _json(diagnostic) if diagnostic else None, _now(), step_run_id))
        self.connection.commit()

    def due_pipelines(self, at: str | None = None) -> list[dict[str, object]]:
        return [self.pipeline(str(row["id"])) for row in self.connection.execute("SELECT id FROM automations WHERE enabled=1 AND next_due_at IS NOT NULL AND next_due_at<=? ORDER BY next_due_at,id", (at or _now(),))]

    def _advance_schedule(self, automation_id: str) -> None:
        pipeline = self.pipeline(automation_id)
        schedule = pipeline["schedule"]
        if schedule["kind"] == "interval":
            next_due = (datetime.now(UTC) + timedelta(seconds=int(schedule["interval_seconds"]))).isoformat()
            self.connection.execute("UPDATE automations SET next_due_at=?,updated_at=? WHERE id=?", (next_due, _now(), automation_id))


def run_pipeline(root: Path, run_id: str, executors: Mapping[str, Callable[[dict[str, object], dict[str, object]], dict[str, object]]] | None = None) -> dict[str, object]:
    store = AutomationStore(root / "automations.sqlite3")
    try:
        run = store.claim_run(run_id)
        pipeline = store.pipeline(str(run["automation_id"]))
        outputs: dict[str, object] = {}
        for step in pipeline["steps"]:
            if store.run_record(run_id)["state"] == "cancel_requested":
                return store.complete_run(run_id, "cancelled")
            dependency_outputs = {key: outputs[key] for key in step["depends_on"]}
            step_input = {"config": step["config"], "dependencies": dependency_outputs}
            failure: Exception | None = None
            for attempt in range(1, int(step["max_retries"]) + 2):
                step_run_id = store._record_step(run_id, step, attempt, "running", step_input)
                try:
                    executor = executors.get(str(step["kind"])) if executors else None
                    output = executor(step, dependency_outputs) if executor else _execute_step(root, store, run_id, step, dependency_outputs)
                    store.finish_step(step_run_id, "succeeded", output)
                    outputs[str(step["key"])] = output
                    failure = None
                    break
                except Exception as error:
                    failure = error
                    store.finish_step(step_run_id, "failed", diagnostic={"code": _diagnostic_code(error), "detail": str(error)})
                    if store.run_record(run_id)["state"] == "cancel_requested":
                        return store.complete_run(run_id, "cancelled")
            if failure is not None:
                return store.complete_run(run_id, "failed", {"code": "FR-AUTO-STEP-FAILED", "step": step["key"], "detail": str(failure)})
        return store.complete_run(run_id, "succeeded")
    except Exception as error:
        try:
            current = store.run_record(run_id)
            if current["state"] in {"running", "cancel_requested"}:
                return store.complete_run(run_id, "failed", {"code": "FR-AUTO-WORKER", "detail": str(error)})
        except Exception:
            pass
        raise
    finally:
        store.close()


def _execute_step(root: Path, store: AutomationStore, run_id: str, step: Mapping[str, object], dependencies: dict[str, object]) -> dict[str, object]:
    kind = str(step["kind"])
    config = dict(step["config"])
    if kind == "model":
        model = str(config["model"])
        prompt = str(config["prompt"])
        if dependencies:
            prompt = f"{prompt}\n\nDependency outputs:\n{json.dumps(dependencies, sort_keys=True)}"
        plan = plan_ollama_inference([model], config.get("context_length"), config.get("cpu_threads"), config.get("batch_size"), config.get("gpu_layers"), str(config.get("keep_alive", "15m")))
        if not plan["supported"]:
            raise RuntimeError(f"FR-INFERENCE-PROFILE: {','.join(plan['reasons'])}")
        stream = stream_ollama(model, prompt, plan["options"], str(plan["keep_alive"]), plan["runtime_probe"])
        chunks = []
        for chunk in stream:
            if store.run_record(run_id)["state"] == "cancel_requested":
                raise RuntimeError("FR-AUTO-CANCELLED")
            chunks.append(chunk)
        return {"model": model, "output": "".join(chunks), "metrics": getattr(stream, "metrics", {})}
    if kind == "skill":
        return _execute_skill(root, str(config["skill_id"]), config, dependencies)
    if kind == "connector":
        return _execute_connector(root, str(config["connector_id"]), config)
    raise ValueError(f"FR-AUTO-STEP-KIND: {kind}")


def _execute_skill(root: Path, skill_id: str, config: dict[str, object], dependencies: dict[str, object]) -> dict[str, object]:
    if skill_id == "evidence-review":
        ledger = ClaimLedger(root / "claims.sqlite3")
        try:
            claims = tuple(Claim(str(record["id"]), str(record["text"]), str(record["claim_type"]), tuple(str(item["evidence_uri"]) for item in record["evidence"])) for record in ledger.list())
            return {"findings": [finding.__dict__ for finding in review_claims(claims)]}
        finally:
            ledger.close()
    if skill_id == "artifact-provenance":
        frontier = FrontierStore(root)
        try:
            artifact_id = str(config.get("artifact_id") or "")
            if artifact_id:
                return {"artifact_id": artifact_id, "versions": frontier.artifact_versions(artifact_id)}
            rows = frontier.connection.execute("SELECT id,name,media_type,created_at FROM artifacts WHERE project_id=? ORDER BY created_at,id", (config["project_id"],))
            return {"artifacts": [dict(row) for row in rows]}
        finally:
            frontier.close()
    if skill_id == "reproducible-kernel":
        kernel = PythonKernel()
        try:
            result = kernel.execute(str(config.get("code") or "print('pipeline ready')"))
            if result.state != "succeeded":
                raise RuntimeError(result.error or "FR-KERNEL-FAILED")
            return {"stdout": result.stdout, "stderr": result.stderr, "dependency_count": len(dependencies)}
        finally:
            kernel.close()
    raise ValueError(f"FR-AUTO-SKILL-UNAVAILABLE: {skill_id}")


def _execute_connector(root: Path, connector_id: str, config: dict[str, object]) -> dict[str, object]:
    if connector_id == "local-literature":
        literature = LiteratureStore(root / "literature.sqlite3")
        try:
            return {"queries": literature.queries()}
        finally:
            literature.close()
    if connector_id == "local-artifacts":
        frontier = FrontierStore(root)
        try:
            rows = frontier.connection.execute("SELECT id,name,media_type,created_at FROM artifacts WHERE project_id=? ORDER BY created_at,id", (config["project_id"],))
            return {"artifacts": [dict(row) for row in rows]}
        finally:
            frontier.close()
    if connector_id == "huggingface-model-catalog":
        return {"models": HuggingFaceHub().search_models(str(config.get("query") or ""), int(config.get("limit") or 10))}
    raise ValueError(f"FR-AUTO-CONNECTOR-UNAVAILABLE: {connector_id}")


def _validate_steps(steps: list[dict[str, object]], project_id: str) -> list[dict[str, object]]:
    if not isinstance(steps, list):
        raise ValueError("Pipeline steps must be a list.")
    if not steps:
        raise ValueError("A pipeline requires at least one step.")
    normalized = []
    keys = set()
    for raw in steps:
        if not isinstance(raw, Mapping):
            raise ValueError("Each pipeline step must be an object.")
        key = str(raw.get("key") or "").strip()
        kind = str(raw.get("kind") or "").strip()
        raw_config = raw.get("config") or {}
        raw_dependencies = raw.get("depends_on") or []
        if not isinstance(raw_config, Mapping):
            raise ValueError(f"Pipeline step config must be an object: {key}")
        if not isinstance(raw_dependencies, list):
            raise ValueError(f"Pipeline step dependencies must be a list: {key}")
        config = dict(raw_config)
        dependencies = [str(item) for item in raw_dependencies]
        retries = int(raw.get("max_retries") or 0)
        if not _STEP_KEY.fullmatch(key) or key in keys:
            raise ValueError(f"Invalid or duplicate pipeline step key: {key}")
        if kind not in PIPELINE_STEP_KINDS:
            raise ValueError(f"Unsupported pipeline step kind: {kind}")
        if retries < 0 or retries > 5:
            raise ValueError("Step retries must be between 0 and 5.")
        external = False
        if kind == "model" and (not str(config.get("model") or "").strip() or not str(config.get("prompt") or "").strip()):
            raise ValueError("Model steps require an exact model and prompt.")
        if kind == "skill":
            skill_id = str(config.get("skill_id") or "")
            if skill_id not in SKILL_EXECUTORS:
                raise ValueError(f"FR-AUTO-SKILL-UNAVAILABLE: {skill_id}")
            config.setdefault("project_id", project_id)
        if kind == "connector":
            connector_id = str(config.get("connector_id") or "")
            if connector_id not in CONNECTOR_EXECUTORS:
                raise ValueError(f"FR-AUTO-CONNECTOR-UNAVAILABLE: {connector_id}")
            if connector_id == "huggingface-model-catalog" and not str(config.get("query") or "").strip():
                raise ValueError("Hugging Face model catalog steps require a query.")
            external = CONNECTOR_EXECUTORS[connector_id]
            config.setdefault("project_id", project_id)
        normalized.append({"key": key, "kind": kind, "config": config, "depends_on": dependencies, "max_retries": retries, "external_effects": external})
        keys.add(key)
    for step in normalized:
        if any(dependency not in keys or dependency == step["key"] for dependency in step["depends_on"]):
            raise ValueError(f"Invalid dependency for pipeline step: {step['key']}")
    return _topological_steps(normalized)


def _topological_steps(steps: list[dict[str, object]]) -> list[dict[str, object]]:
    remaining = list(steps)
    completed: set[str] = set()
    ordered = []
    while remaining:
        ready = [step for step in remaining if set(step["depends_on"]).issubset(completed)]
        if not ready:
            raise ValueError("Pipeline dependencies contain a cycle.")
        for step in ready:
            ordered.append(step)
            completed.add(str(step["key"]))
            remaining.remove(step)
    return ordered


def _validate_schedule(schedule: Mapping[str, object]) -> tuple[dict[str, object], str | None]:
    kind = str(schedule.get("kind") or "manual")
    if kind == "manual":
        return {"kind": "manual"}, None
    if kind != "interval":
        raise ValueError("Schedule kind must be manual or interval.")
    seconds = int(schedule.get("interval_seconds") or 0)
    if seconds < 60 or seconds > 31_536_000:
        raise ValueError("Schedule interval must be between 60 seconds and one year.")
    return {"kind": "interval", "interval_seconds": seconds}, (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()


def _diagnostic_code(error: Exception) -> str:
    text = str(error)
    return text.split(":", 1)[0] if text.startswith("FR-") else "FR-AUTO-STEP"
