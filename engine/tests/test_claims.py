import tempfile
import unittest
from pathlib import Path

from frontier_engine.claims import ClaimLedger


class ClaimLedgerTests(unittest.TestCase):
    def test_claims_keep_type_uncertainty_and_exact_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = ClaimLedger(Path(directory) / "claims.sqlite3")
            claim_id = ledger.create("computed", "QC rate declined", "Dataset is a fixture.", [("artifact://qc", "table:row-2")])
            ledger.set_status(claim_id, "supported")
            record = ledger.list()[0]
            self.assertEqual(record["status"], "supported")
            self.assertEqual(record["evidence"][0]["selector"], "table:row-2")
            ledger.close()
