import tempfile,unittest
from pathlib import Path
from frontier_engine.notifications import NotificationStore
class NotificationTests(unittest.TestCase):
 def test_pending_acknowledgement_and_sensitive_body_rejection(self)->None:
  with tempfile.TemporaryDirectory() as directory:
   store=NotificationStore(Path(directory)/"notify.sqlite3");identifier=store.create("job/run-1","warning","Job needs input","Select a model","frontier://jobs/run-1")
   self.assertEqual(store.pending()[0].id,identifier);store.acknowledge(identifier);self.assertEqual(store.pending(),())
   with self.assertRaises(ValueError):store.create("provider","error","Bad key","Bearer secret","frontier://settings")
   store.close()
