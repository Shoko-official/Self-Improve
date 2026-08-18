"""Capability-gated local agent execution with inspectable state."""

from __future__ import annotations

import json
from collections.abc import Iterator

from frontier_engine.agent_state import AgentStateStore
from frontier_engine.integration_registry import apply_skill_instructions
from frontier_engine.runtimes import stream_ollama


def run_local_agent(state: AgentStateStore, project_id: str, model: str, prompt: str, stream: Iterator[str] | None = None, skill_ids: list[str] | None = None) -> dict[str, object]:
    if not prompt.strip():
        raise ValueError("An agent prompt is required.")
    compiled_prompt, selected_skills = apply_skill_instructions(prompt, skill_ids or [])
    state.set_plan(project_id, "Run the requested local task and record the output.")
    todo_id = state.add_todo(project_id, "Run local model")
    state.transition_todo(todo_id, "in_progress")
    request = json.dumps({"model": model, "skills": selected_skills}, sort_keys=True)
    try:
        output = "".join(stream if stream is not None else stream_ollama(model, compiled_prompt))
    except Exception as error:
        state.record_tool_call(project_id, "agent.generate", request, "failed", json.dumps({"error": str(error)}))
        state.transition_todo(todo_id, "failed")
        raise
    state.record_tool_call(project_id, "agent.generate", request, "succeeded", json.dumps({"output_chars": len(output)}))
    state.transition_todo(todo_id, "completed")
    return {"project_id": project_id, "model": model, "output": output, "skills": selected_skills, "plan": state.plan(project_id), "todos": [todo.__dict__ for todo in state.todos(project_id)]}
