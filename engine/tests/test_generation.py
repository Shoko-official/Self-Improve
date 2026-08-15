import tempfile
import unittest
from pathlib import Path

from frontier_engine.generation import run_generation
from frontier_engine.store import FrontierStore


class GenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.store = FrontierStore(Path(self.directory.name))
        self.project_id = self.store.create_project("Generation")

    def tearDown(self) -> None:
        self.store.close()
        self.directory.cleanup()

    def test_generation_persists_streamed_output_and_reopens(self) -> None:
        generation_id = self.store.create_generation(self.project_id, "ollama", "test-model", "Explain")
        self.assertEqual("".join(run_generation(self.store, generation_id, iter(("hello ", "world")))), "hello world")
        record = self.store.generation(generation_id)
        self.assertEqual(record["state"], "succeeded")
        self.assertEqual(record["output"], "hello world")
        self.assertEqual(record["result"], {"chunk_count": 2, "output_chars": 11})

    def test_generation_cancellation_stops_before_next_chunk(self) -> None:
        generation_id = self.store.create_generation(self.project_id, "ollama", "test-model", "Stop")

        def stream() -> object:
            yield "first"
            self.store.request_cancellation(self.store.generation(generation_id)["job_id"])
            yield "second"

        self.assertEqual(list(run_generation(self.store, generation_id, stream())), ["first"])
        record = self.store.generation(generation_id)
        self.assertEqual(record["state"], "cancelled")
        self.assertEqual(record["output"], "first")

    def test_generation_failure_has_durable_diagnostic(self) -> None:
        generation_id = self.store.create_generation(self.project_id, "ollama", "test-model", "Fail")

        def stream() -> object:
            yield "partial"
            raise RuntimeError("adapter stopped")

        with self.assertRaisesRegex(RuntimeError, "adapter stopped"):
            list(run_generation(self.store, generation_id, stream()))
        record = self.store.generation(generation_id)
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["output"], "partial")
        self.assertEqual(record["diagnostic"]["code"], "FR-GENERATION-STREAM")
