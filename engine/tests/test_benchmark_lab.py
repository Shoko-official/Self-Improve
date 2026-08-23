import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_engine.benchmark_lab import audit_task, list_benchmark_runs, run_benchmark


class BenchmarkLabTests(unittest.TestCase):
    def test_strict_audit_rejects_wrong_rag_interval(self) -> None:
        result = audit_task("agentic-rag", "agentic-rag", "No causal control was run [source:lab-notes.md:0-72]. B-17 [source:lab-notes.md:73-121].")
        self.assertFalse(result["checks"]["causal_abstention"])
        self.assertFalse(result["checks"]["no_wrong_interval"])

    def test_run_persists_raw_outputs_and_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "model.gguf"
            model.write_bytes(b"fixture")

            def output(_root: Path, _model: Path, prompt: str, *, max_tokens: int):
                if "top_k" in prompt:
                    return iter(["```python\ndef top_k(values, k): return sorted(values, reverse=True)[:k]\n```"])
                raise RuntimeError("fixture runtime failure")

            with patch("frontier_engine.benchmark_lab.stream_managed_gguf", side_effect=output):
                report = run_benchmark(root, model, 128, "fixture")

            self.assertEqual(report["status"], "failed")
            self.assertEqual(sum(item["failure"] is not None for item in report["tasks"]), 5)
            report_path = Path(report["report_path"])
            self.assertTrue(report_path.is_file())
            self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["run_id"], report["run_id"])
            listing = list_benchmark_runs(root)["runs"]
            self.assertEqual(listing[0]["run_id"], report["run_id"])
            self.assertEqual(listing[0]["latency_ms"], sum(item["latency_ms"] for item in report["tasks"]))


if __name__ == "__main__":
    unittest.main()
