import json
import unittest
from pathlib import Path


class TauriBundleTests(unittest.TestCase):
    def test_runtime_pack_manifests_are_declared_as_resources(self) -> None:
        config = json.loads((Path(__file__).parents[2] / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        resources = config["bundle"]["resources"]
        self.assertIn("../runtime-packs", resources)
        self.assertTrue((Path(__file__).parents[2] / "runtime-packs" / "ollama" / "manifest.json").is_file())
