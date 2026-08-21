import tempfile
import unittest
from pathlib import Path

from frontier_engine.cli import archive_project, create_project, projects, restore_project


class ProjectRestoreTests(unittest.TestCase):
    def test_restore_returns_an_archived_project_to_the_active_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_id = create_project(root, "Restorable project")["id"]
            archive_project(root, project_id)

            restored = restore_project(root, project_id)
            project = next(item for item in projects(root)["projects"] if item["id"] == project_id)

        self.assertEqual(restored, {"id": project_id, "archived": False})
        self.assertIsNone(project["archived_at"])


if __name__ == "__main__":
    unittest.main()
