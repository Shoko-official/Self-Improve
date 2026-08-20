import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_engine.agent_runner import run_local_agent
from frontier_engine.agent_state import AgentStateStore


class AgentRunnerTests(unittest.TestCase):
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
