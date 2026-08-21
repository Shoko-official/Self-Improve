import subprocess
import tempfile
import unittest
from pathlib import Path

from frontier_engine.cli import create_project, grant_project_folder, project_git_diff


class ProjectGitDiffTests(unittest.TestCase):
    def test_diff_reports_changed_tracked_files_without_mutating_the_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "state"
            repository = Path(temp_dir) / "repository"
            repository.mkdir()
            subprocess.run(["git", "init", "-b", "main", str(repository)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repository), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repository), "config", "user.name", "Test User"], check=True)
            note = repository / "note.txt"
            note.write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "note.txt"], check=True)
            subprocess.run(["git", "-C", str(repository), "commit", "-m", "initial"], check=True, capture_output=True)
            note.write_text("after\n", encoding="utf-8")
            project = create_project(root, "Git diff")
            grant_project_folder(root, project["id"], repository, "read")

            result = project_git_diff(root, project["id"])

        self.assertTrue(result["repository"])
        self.assertEqual(result["files"], ["M note.txt"])
        self.assertIn("-before", result["preview"])
        self.assertIn("+after", result["preview"])
        self.assertFalse(result["truncated"])


if __name__ == "__main__":
    unittest.main()
