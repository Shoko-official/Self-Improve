import tempfile, unittest
from pathlib import Path
from frontier_engine.annotations import AnnotationStore

class AnnotationTests(unittest.TestCase):
 def test_annotations_stay_on_exact_version_and_consume_once(self) -> None:
  with tempfile.TemporaryDirectory() as directory:
   store=AnnotationStore(Path(directory)/"annotations.sqlite3")
   identifier=store.create("artifact-v1","pdf_region",{"page":2,"x":.2},"Explain this peak")
   store.create("artifact-v2","pdf_region",{"page":2,"x":.2},"Version two")
   self.assertEqual([item.id for item in store.list_open("artifact-v1")],[identifier])
   consumed=store.consume((identifier,)); self.assertEqual(consumed[0].artifact_version_id,"artifact-v1")
   self.assertEqual(store.list_open("artifact-v1"),())
   with self.assertRaises(ValueError): store.consume((identifier,))
   store.close()
