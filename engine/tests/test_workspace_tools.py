import tempfile
import unittest
from pathlib import Path

from frontier_engine.agent_state import AgentStateStore
from frontier_engine.store import ArchivedProjectError, FrontierStore
from frontier_engine.workspace_tools import ProjectWorkspaceTools, WorkspaceToolDenied


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(); root = Path(self.directory.name)
        self.store = FrontierStore(root / "state"); self.agent = AgentStateStore(root / "agent.sqlite3")
        self.project_id = self.store.create_project("Workspace"); self.workspace = root / "workspace"; self.workspace.mkdir()
        self.tools = ProjectWorkspaceTools(self.store, self.agent, self.project_id, self.workspace)

    def tearDown(self) -> None:
        self.agent.close(); self.store.close(); self.directory.cleanup()

    def test_tools_require_exact_grants_and_record_success(self) -> None:
        with self.assertRaises(WorkspaceToolDenied): self.tools.write_file("notes.txt", "hello")
        self.store.grant_project_folder(self.project_id, self.workspace, "write")
        self.assertEqual(self.tools.write_file("notes.txt", "hello").read_text(), "hello")
        self.store.grant_project_folder(self.project_id, self.workspace, "read")
        self.assertEqual(self.tools.read_file("notes.txt"), "hello")
        self.assertEqual(self.tools.list_files(), ("notes.txt",))
        self.assertEqual([row["state"] for row in self.agent.tool_calls(self.project_id)], ["failed", "succeeded", "succeeded", "succeeded"])

    def test_tools_reject_traversal_and_archived_project_writes(self) -> None:
        self.store.grant_project_folder(self.project_id, self.workspace, "write")
        with self.assertRaisesRegex(ValueError, "PATH"): self.tools.read_file("../secret.txt")
        self.store.archive_project(self.project_id)
        with self.assertRaises(ArchivedProjectError): self.tools.write_file("notes.txt", "no")
