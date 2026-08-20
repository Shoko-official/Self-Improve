"""Capability-gated local agent execution with inspectable state."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from frontier_engine.agent_state import AgentStateStore
from frontier_engine.integration_registry import apply_skill_instructions
from frontier_engine.managed_gguf import stream_managed_gguf
from frontier_engine.runtimes import stream_ollama
from frontier_engine.system_prompt import build_system_prompt


def run_local_agent(state: AgentStateStore, project_id: str, model: str, prompt: str, stream: Iterator[str] | None = None, skill_ids: list[str] | None = None, access_mode: str = "ask", reasoning_effort: str = "standard", runtime_root: Path | None = None, project_name: str = "Local project", project_instructions: str = "", folders: list[str] | None = None, work_mode: str = "chat") -> dict[str, object]:
    if not prompt.strip():
        raise ValueError("An agent prompt is required.")
    if access_mode not in {"read", "ask", "full"}:
        raise ValueError("Invalid agent access mode.")
    if reasoning_effort not in {"compact", "standard", "extended"}:
        raise ValueError("Invalid reasoning effort.")
    compiled_prompt, selected_skills = apply_skill_instructions(prompt, skill_ids or [])
    capabilities = ["generation.response", *(f"skill.instructions:{item['id']}" for item in selected_skills)]
    system_prompt = build_system_prompt(project_name, project_instructions, access_mode, reasoning_effort, folders or [], work_mode, capabilities)
    compiled_prompt = f"<system>\n{system_prompt}\n</system>\n\n<user>\n{compiled_prompt}\n</user>"
    state.set_plan(project_id, "Run the requested local task and record the output.")
    todo_id = state.add_todo(project_id, "Run local model")
    state.transition_todo(todo_id, "in_progress")
    request = json.dumps({"access_mode": access_mode, "model": model, "reasoning_effort": reasoning_effort, "skills": selected_skills, "work_mode": work_mode}, sort_keys=True)
    try:
        if stream is not None:
            chunks = stream
        elif model.startswith("gguf:"):
            chunks = stream_managed_gguf(runtime_root or Path.home() / ".frontier-data", Path(model.removeprefix("gguf:")), compiled_prompt)
        else:
            chunks = stream_ollama(model, compiled_prompt)
        output = "".join(chunks)
    except Exception as error:
        state.record_tool_call(project_id, "agent.generate", request, "failed", json.dumps({"error": str(error)}))
        state.transition_todo(todo_id, "failed")
        raise
    state.record_tool_call(project_id, "agent.generate", request, "succeeded", json.dumps({"output_chars": len(output)}))
    state.transition_todo(todo_id, "completed")
    return {"project_id": project_id, "model": model, "output": output, "skills": selected_skills, "access_mode": access_mode, "reasoning_effort": reasoning_effort, "work_mode": work_mode, "system_prompt": system_prompt, "plan": state.plan(project_id), "todos": [todo.__dict__ for todo in state.todos(project_id)]}
