import tempfile
import unittest
from pathlib import Path

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
