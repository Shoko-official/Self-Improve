import tempfile
import unittest
from pathlib import Path

from frontier_engine.model_registry import ModelRegistry


class ModelRegistryTests(unittest.TestCase):
    def test_import_records_hash_without_claiming_runtime_support(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); model = root / "fixture.gguf"; model.write_bytes(b"model")
            registry = ModelRegistry(root / "models.sqlite3")
            self.assertEqual(registry.register(model)["capability_state"], "unvalidated")
            self.assertEqual(registry.list()[0]["format"], "gguf")
            registry.close()
