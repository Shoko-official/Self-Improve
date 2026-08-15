import tempfile
import unittest
from pathlib import Path

from frontier_engine.literature import LiteratureStore


class LiteratureTests(unittest.TestCase):
    def test_query_and_evidence_keep_reproducible_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LiteratureStore(Path(directory) / "literature.sqlite3")
            query_id = store.record_query("single cell QC", "fixture", '{"year": 2025}', 1)
            store.record_evidence(query_id, "doi:10.example/test", "QC paper", "Inspected methods excerpt", "https://example.test/full", "published", "not_retracted")
            self.assertEqual(store.queries()[0]["source"], "fixture")
            self.assertEqual(store.evidence(query_id)[0]["retraction_state"], "not_retracted")
            store.close()
