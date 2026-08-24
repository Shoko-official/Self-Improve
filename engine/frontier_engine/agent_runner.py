"""Capability-gated local agent execution with inspectable state."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

from frontier_engine.agent_state import AgentStateStore
from frontier_engine.integration_registry import apply_skill_instructions
from frontier_engine.managed_gguf import stream_managed_gguf
from frontier_engine.runtimes import stream_ollama
from frontier_engine.store import FrontierStore
from frontier_engine.system_prompt import build_system_prompt
from frontier_engine.workspace_tools import ProjectWorkspaceTools


_TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)
_MAX_TOOL_TURNS = 3


def parse_tool_calls(output: str) -> tuple[dict[str, object], ...]:
    """Parse only the explicit, bounded tool envelope emitted by the model."""
    calls: list[dict[str, object]] = []
    for match in _TOOL_CALL_PATTERN.finditer(output):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            calls.append({"name": "", "arguments": {}, "error": "FR-AGENT-TOOL-MALFORMED"})
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("name"), str) or not isinstance(payload.get("arguments", {}), dict):
            calls.append({"name": "", "arguments": {}, "error": "FR-AGENT-TOOL-MALFORMED"})
            continue
        calls.append({"name": payload["name"], "arguments": payload.get("arguments", {})})
    return tuple(calls)


def run_local_agent(
    state: AgentStateStore,
    project_id: str,
    model: str,
    prompt: str,
    stream: Iterator[str] | None = None,
    skill_ids: list[str] | None = None,
    access_mode: str = "ask",
    reasoning_effort: str = "standard",
    runtime_root: Path | None = None,
    project_name: str = "Local project",
    project_instructions: str = "",
    folders: list[str] | None = None,
    work_mode: str = "chat",
    workspace: Path | None = None,
    frontier_store: FrontierStore | None = None,
) -> dict[str, object]:
    if not prompt.strip():
        raise ValueError("An agent prompt is required.")
    if access_mode not in {"read", "ask", "full"}:
        raise ValueError("Invalid agent access mode.")
    if reasoning_effort not in {"compact", "standard", "extended"}:
        raise ValueError("Invalid reasoning effort.")
    compiled_prompt, selected_skills = apply_skill_instructions(prompt, skill_ids or [])
    workspace_tools = None
    if workspace is not None and frontier_store is not None and workspace.is_dir():
        workspace_tools = ProjectWorkspaceTools(frontier_store, state, project_id, workspace)
    capabilities = ["generation.response", *(f"skill.instructions:{item['id']}" for item in selected_skills)]
    if workspace_tools is not None:
        capabilities.extend(("workspace.list", "workspace.read", "workspace.write"))
    system_prompt = build_system_prompt(project_name, project_instructions, access_mode, reasoning_effort, folders or [], work_mode, capabilities)
    compiled_prompt = f"<system>\n{system_prompt}\n</system>\n\n<user>\n{compiled_prompt}\n</user>"
    state.set_plan(project_id, "Run the requested local task and record the output.")
    todo_id = state.add_todo(project_id, "Run local model")
    state.transition_todo(todo_id, "in_progress")
    request_base = {"access_mode": access_mode, "model": model, "reasoning_effort": reasoning_effort, "skills": selected_skills, "work_mode": work_mode}
    model_prompt = compiled_prompt
    visible_outputs: list[str] = []
    try:
        for turn in range(_MAX_TOOL_TURNS):
            chunks = stream if turn == 0 and stream is not None else _stream_model(model, runtime_root, model_prompt)
            output = "".join(chunks)
            calls = parse_tool_calls(output)
            visible = _TOOL_CALL_PATTERN.sub("", output).strip()
            if visible:
                visible_outputs.append(visible)
            state.record_tool_call(project_id, "agent.generate", json.dumps({**request_base, "turn": turn}, sort_keys=True), "succeeded", json.dumps({"output_chars": len(output), "tool_calls": len(calls)}))
            if not calls or workspace_tools is None:
                break
            results: list[dict[str, object]] = []
            for call in calls:
                result = _execute_tool(workspace_tools, access_mode, call)
                results.append({"name": call.get("name"), "result": result})
            model_prompt = f"{compiled_prompt}\n\n<assistant_turn>\n{output}\n</assistant_turn>\n\n<tool_results>\n{json.dumps(results, sort_keys=True)}\n</tool_results>\n\nContinue the task using only these host results. Do not repeat a completed tool call unless the result requires it."
        state.transition_todo(todo_id, "completed")
    except Exception as error:
        state.record_tool_call(project_id, "agent.generate", json.dumps(request_base, sort_keys=True), "failed", json.dumps({"error": str(error)}))
        state.transition_todo(todo_id, "failed")
        raise
    return {"project_id": project_id, "model": model, "output": "\n\n".join(visible_outputs), "skills": selected_skills, "access_mode": access_mode, "reasoning_effort": reasoning_effort, "work_mode": work_mode, "system_prompt": system_prompt, "plan": state.plan(project_id), "todos": [todo.__dict__ for todo in state.todos(project_id)]}


def _stream_model(model: str, runtime_root: Path | None, prompt: str) -> Iterator[str]:
    if model.startswith("gguf:"):
        return stream_managed_gguf(runtime_root or Path.home() / ".frontier-data", Path(model.removeprefix("gguf:")), prompt)
    return stream_ollama(model, prompt)


def _execute_tool(tools: ProjectWorkspaceTools, access_mode: str, call: dict[str, object]) -> dict[str, object]:
    name = call.get("name")
    arguments = call.get("arguments")
    if call.get("error"):
        result = {"error": call["error"]}
        tools.agent_state.record_tool_call(tools.project_id, "agent.tool", json.dumps(call, sort_keys=True), "failed", json.dumps(result, sort_keys=True))
        return result
    if not isinstance(arguments, dict):
        result = {"error": "FR-AGENT-TOOL-MALFORMED"}
        tools.agent_state.record_tool_call(tools.project_id, "agent.tool", json.dumps(call, sort_keys=True), "failed", json.dumps(result, sort_keys=True))
        return result
    try:
        if name == "workspace.list" and not arguments:
            return {"files": tools.list_files()}
        if name == "workspace.read" and isinstance(arguments.get("path"), str):
            return {"path": arguments["path"], "content": tools.read_file(arguments["path"])}
        if name == "workspace.write" and isinstance(arguments.get("path"), str) and isinstance(arguments.get("content"), str):
            if access_mode != "full":
                result = {"error": "FR-AGENT-WRITE-APPROVAL-REQUIRED", "path": arguments["path"]}
                tools.agent_state.record_tool_call(tools.project_id, "workspace.write", json.dumps(arguments, sort_keys=True), "approval_required", json.dumps(result, sort_keys=True))
                return result
            return {"path": arguments["path"], "written": str(tools.write_file(arguments["path"], arguments["content"]))}
    except Exception as error:
        return {"error": str(error)}
    result = {"error": "FR-AGENT-TOOL-UNKNOWN"}
    tools.agent_state.record_tool_call(tools.project_id, "agent.tool", json.dumps(call, sort_keys=True), "failed", json.dumps(result, sort_keys=True))
    return result
