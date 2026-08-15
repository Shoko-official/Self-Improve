import tempfile
import unittest
from pathlib import Path
from frontier_engine.permissions import PermissionLedger

class PermissionLedgerTests(unittest.TestCase):
 def test_exact_scope_once_and_revocation(self) -> None:
  with tempfile.TemporaryDirectory() as directory:
   ledger=PermissionLedger(Path(directory)/"permissions.sqlite3")
   grant=ledger.grant("s3://lab/a", "write")
   self.assertFalse(ledger.authorize("s3://lab/b", "write"))
   self.assertTrue(ledger.authorize("s3://lab/a", "write")); self.assertFalse(ledger.authorize("s3://lab/a", "write"))
   persistent=ledger.grant("ssh://cluster", "submit", "until_revoked")
   self.assertTrue(ledger.authorize("ssh://cluster", "submit")); ledger.revoke(persistent)
   self.assertFalse(ledger.authorize("ssh://cluster", "submit")); ledger.close()
