import tempfile
import unittest
from pathlib import Path

from scripts.release_gate import run_gate


class ReleaseGateTests(unittest.TestCase):
    def test_gate_reports_complete_repository_evidence(self) -> None:
        result = run_gate(Path(__file__).parents[2], require_clean=False)
        self.assertTrue(result["passed"])

    def test_gate_reports_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_gate(Path(directory), require_clean=False)
            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"][0]["passed"])
