import sys
import tempfile
import unittest
from pathlib import Path

from frontier_engine.shell import ShellPermissionDenied, execute_project_shell
from frontier_engine.store import FrontierStore


class ShellTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = FrontierStore(self.root / "state")
        self.project_id = self.store.create_project("Shell")
        self.workdir = self.root / "workspace"
        self.workdir.mkdir()

    def tearDown(self) -> None:
        self.store.close()
        self.directory.cleanup()

    def test_shell_requires_a_project_working_directory_grant(self) -> None:
        with self.assertRaisesRegex(ShellPermissionDenied, "PERMISSION"):
            execute_project_shell(self.store, self.project_id, self.workdir, (sys.executable, "-c", "print('no')"))

    def test_shell_persists_success_and_nonzero_exit(self) -> None:
        self.store.grant_project_folder(self.project_id, self.workdir, "write")
        success = execute_project_shell(self.store, self.project_id, self.workdir, (sys.executable, "-c", "print('complete')"))
        self.assertEqual((success["state"], success["result"]["stdout"]), ("succeeded", "complete\n"))
        failure = execute_project_shell(self.store, self.project_id, self.workdir, (sys.executable, "-c", "raise SystemExit(7)"))
        self.assertEqual((failure["state"], failure["diagnostic"]["code"]), ("failed", "FR-SHELL-EXIT"))

    def test_shell_timeout_is_durable(self) -> None:
        self.store.grant_project_folder(self.project_id, self.workdir, "write")
        result = execute_project_shell(self.store, self.project_id, self.workdir, (sys.executable, "-c", "import time; time.sleep(1)"), 0.01)
        self.assertEqual((result["state"], result["diagnostic"]["code"]), ("failed", "FR-SHELL-TIMEOUT"))
