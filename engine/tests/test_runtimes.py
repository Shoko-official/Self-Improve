import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_engine.runtimes import LocalRuntimeUnavailable, RuntimeManifest, probe_lm_studio_library, probe_ollama, stream_ollama, stream_ollama_pull


class RuntimeTests(unittest.TestCase):
    def test_manifest_validates_contract_and_support(self) -> None:
        manifest = RuntimeManifest.load(Path("runtime-packs/ollama/manifest.json"))
        self.assertTrue(manifest.supports("text", "stream", "ollama"))
        self.assertFalse(manifest.supports("image", "generate", "ollama"))

    def test_manifest_rejects_missing_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"; path.write_text(json.dumps({"id": "bad"}))
            with self.assertRaisesRegex(ValueError, "missing fields"):
                RuntimeManifest.load(path)

    def test_ollama_probe_never_claims_a_missing_binary_works(self) -> None:
        with patch("frontier_engine.runtimes.shutil.which", return_value=None):
            result = probe_ollama()
        self.assertEqual(result, {"runtime": "ollama", "available": False, "reason": "FR-RUNTIME-OLLAMA-NOT-FOUND", "models": []})

    def test_generation_refuses_an_unavailable_runtime(self) -> None:
        with patch("frontier_engine.runtimes.probe_ollama", return_value={"available": False, "reason": "FR-RUNTIME-OLLAMA-NOT-FOUND"}):
            with self.assertRaisesRegex(LocalRuntimeUnavailable, "NOT-FOUND"):
                next(stream_ollama("missing", "hello"))

    def test_pull_refuses_a_missing_runtime_without_a_fallback(self) -> None:
        with patch("frontier_engine.runtimes.shutil.which", return_value=None):
            with self.assertRaisesRegex(LocalRuntimeUnavailable, "NOT-FOUND"):
                next(stream_ollama_pull("qwen3"))

    def test_lm_studio_library_discovers_gguf_without_using_lm_studio_for_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            models = home / "external-models"
            model = models / "publisher" / "model" / "model-q4.gguf"
            projection = model.with_name("mmproj-model.gguf")
            model.parent.mkdir(parents=True)
            model.write_bytes(b"gguf")
            projection.write_bytes(b"projection")
            settings = home / ".lmstudio" / "settings.json"
            settings.parent.mkdir()
            settings.write_text(json.dumps({"downloadsFolder": str(models)}), encoding="utf-8")

            with patch("frontier_engine.runtimes.Path.home", return_value=home):
                result = probe_lm_studio_library()

            self.assertTrue(result["available"])
            self.assertEqual(len(result["models"]), 1)
            self.assertEqual(result["models"][0]["path"], str(model.resolve()))
            self.assertEqual(result["models"][0]["execution_runtime"], "shoko-managed-gguf")
