import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_engine.agent_runner import parse_tool_calls, run_local_agent
from frontier_engine.agent_state import AgentStateStore
from frontier_engine.store import FrontierStore


class AgentRunnerTests(unittest.TestCase):
    def test_tool_call_parser_fails_closed(self) -> None:
        self.assertEqual(parse_tool_calls('<tool_call>{"name":"workspace.list","arguments":{}}</tool_call>')[0]["name"], "workspace.list")
        self.assertEqual(parse_tool_calls("<tool_call>{bad}</tool_call>")[0]["error"], "FR-AGENT-TOOL-MALFORMED")

    def test_unknown_tool_is_recorded_as_a_failed_host_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); workspace = root / "workspace"; workspace.mkdir(); frontier = FrontierStore(root / "frontier.sqlite3"); project_id = frontier.create_project("Fixture"); frontier.grant_project_folder(project_id, workspace, "read")
            state = AgentStateStore(root / "agent.sqlite3")
            first = iter(['<tool_call>{"name":"workspace.delete","arguments":{}}</tool_call>'])
            with patch("frontier_engine.agent_runner.stream_ollama", return_value=iter(["The tool is unavailable."])):
                run_local_agent(state, project_id, "fixture", "Delete the fixture", first, access_mode="read", workspace=workspace, frontier_store=frontier)
            self.assertTrue(any(call["tool_name"] == "agent.tool" and call["state"] == "failed" for call in state.tool_calls(project_id)))
            state.close(); frontier.close()

    def test_local_agent_persists_a_plan_todo_and_activity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = AgentStateStore(Path(directory) / "agent.sqlite3")
            result = run_local_agent(state, "project", "fixture", "summarize", iter(["local ", "output"]))
            self.assertEqual(result["output"], "local output")
            self.assertEqual(result["todos"][0]["state"], "completed")
            self.assertEqual(state.tool_calls("project")[0]["state"], "succeeded")
            state.close()

    def test_local_agent_persists_access_and_reasoning_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = AgentStateStore(Path(directory) / "agent.sqlite3")
            result = run_local_agent(state, "project", "fixture", "inspect", iter(["done"]), access_mode="read", reasoning_effort="extended")
            request = json.loads(state.tool_calls("project")[0]["request"])
            self.assertEqual(result["access_mode"], "read")
            self.assertEqual(result["reasoning_effort"], "extended")
            self.assertEqual(request["access_mode"], "read")
            self.assertEqual(request["reasoning_effort"], "extended")
            state.close()

    def test_local_agent_compiles_plan_mode_and_selected_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = AgentStateStore(Path(directory) / "agent.sqlite3")
            result = run_local_agent(state, "project", "fixture", "plan this", iter(["done"]), work_mode="plan")
            request = json.loads(state.tool_calls("project")[0]["request"])
            self.assertEqual(result["work_mode"], "plan")
            self.assertEqual(request["work_mode"], "plan")
            self.assertIn('<work_mode name="plan">', result["system_prompt"])
            self.assertIn("generation.response", result["system_prompt"])
            state.close()

    def test_local_agent_rejects_unknown_access_and_reasoning_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = AgentStateStore(Path(directory) / "agent.sqlite3")
            with self.assertRaisesRegex(ValueError, "access mode"):
                run_local_agent(state, "project", "fixture", "inspect", iter(["done"]), access_mode="unsafe")
            with self.assertRaisesRegex(ValueError, "reasoning effort"):
                run_local_agent(state, "project", "fixture", "inspect", iter(["done"]), reasoning_effort="unbounded")
            state.close()

    def test_local_agent_routes_gguf_paths_to_the_shoko_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = AgentStateStore(root / "agent.sqlite3")
            model = root / "model.gguf"
            model.write_bytes(b"gguf")
            with patch("frontier_engine.agent_runner.stream_managed_gguf", return_value=iter(["local gguf"])) as stream:
                result = run_local_agent(state, "project", f"gguf:{model}", "inspect", runtime_root=root)
            self.assertEqual(result["output"], "local gguf")
            self.assertEqual(stream.call_args.args[0], root)
            self.assertEqual(stream.call_args.args[1], model)
            state.close()

    def test_local_agent_executes_a_typed_workspace_read_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); workspace = root / "workspace"; workspace.mkdir(); (workspace / "README.md").write_text("fixture", encoding="utf-8")
            frontier = FrontierStore(root / "frontier.sqlite3"); project_id = frontier.create_project("Fixture"); frontier.grant_project_folder(project_id, workspace, "read")
            state = AgentStateStore(root / "agent.sqlite3")
            first = iter(['<tool_call>{"name":"workspace.read","arguments":{"path":"README.md"}}</tool_call>'])
            with patch("frontier_engine.agent_runner.stream_ollama", return_value=iter(["The file says fixture."])) as follow_up:
                result = run_local_agent(state, project_id, "fixture", "Read the fixture", first, access_mode="read", workspace=workspace, frontier_store=frontier)
            self.assertIn("The file says fixture.", result["output"])
            self.assertIn("workspace.read", result["system_prompt"])
            self.assertIn("relative to the linked folder", result["system_prompt"])
            self.assertEqual(follow_up.call_count, 1)
            self.assertTrue(any(call["tool_name"] == "workspace.read" for call in state.tool_calls(project_id)))
            state.close(); frontier.close()

    def test_local_agent_write_requires_full_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); workspace = root / "workspace"; workspace.mkdir(); frontier = FrontierStore(root / "frontier.sqlite3"); project_id = frontier.create_project("Fixture"); frontier.grant_project_folder(project_id, workspace, "write")
            state = AgentStateStore(root / "agent.sqlite3")
            first = iter(['<tool_call>{"name":"workspace.write","arguments":{"path":"note.txt","content":"blocked"}}</tool_call>'])
            with patch("frontier_engine.agent_runner.stream_ollama", return_value=iter(["The write needs approval."])):
                run_local_agent(state, project_id, "fixture", "Write the note", first, access_mode="ask", workspace=workspace, frontier_store=frontier)
            self.assertFalse((workspace / "note.txt").exists())
            self.assertTrue(any(call["state"] == "approval_required" for call in state.tool_calls(project_id)))
            state.close(); frontier.close()
