import tempfile,unittest
from pathlib import Path
from frontier_engine.automations import AutomationStore
class AutomationTests(unittest.TestCase):
 def test_dry_run_is_durable_and_external_effects_need_approval(self)->None:
  with tempfile.TemporaryDirectory() as directory:
   store=AutomationStore(Path(directory)/"automations.sqlite3");identifier=store.create("Export","external publish report")
   self.assertEqual(store.run(identifier).state,"simulated")
   with self.assertRaises(PermissionError):store.run(identifier,False)
   self.assertEqual(store.run(identifier,False,True).state,"completed");self.assertEqual(len(store.history(identifier)),2);store.close()
