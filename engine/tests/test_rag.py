import tempfile
import unittest
from pathlib import Path

from frontier_engine.rag import HybridIndex


class StaticEmbedder:
    def embed(self, text: str) -> list[float]:
        normalized = text.lower()
        return [float("hydrogen" in normalized), float("genome" in normalized)]


class HybridIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_lexical_search_exposes_exact_citation_offsets(self) -> None:
        index = HybridIndex(Path(self.temp_dir.name) / "rag.sqlite3")
        index.ingest("file:///papers/hydrogen.md", "Hydrogen paper", "Hydrogen stores energy.\n\nThe catalyst is nickel.")
        result = index.search("hydrogen")[0]
        self.assertEqual(result.source_uri, "file:///papers/hydrogen.md")
        self.assertEqual(result.text, "Hydrogen stores energy.")
        self.assertEqual(result.start_offset, 0)
        self.assertEqual(result.retrieval_mode, "lexical")
        index.close()

    def test_hybrid_search_and_held_out_evaluation_use_supplied_embedder(self) -> None:
        index = HybridIndex(Path(self.temp_dir.name) / "rag.sqlite3", StaticEmbedder())
        index.ingest("file:///papers/hydrogen.md", "Hydrogen paper", "Hydrogen stores energy.")
        index.ingest("file:///papers/genome.md", "Genome paper", "Genome tracks need coordinates.")
        result = index.search("hydrogen fuel")[0]
        metrics = index.evaluate([("genome browser", {"file:///papers/genome.md"})])
        self.assertEqual(result.retrieval_mode, "hybrid")
        self.assertEqual(result.source_uri, "file:///papers/hydrogen.md")
        self.assertEqual(metrics, {"cases": 1, "hits": 1, "recall_at_k": 1.0})
        index.close()
