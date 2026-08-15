import unittest
from frontier_engine.storage import StorageApprovalRequired,StorageProfile,authorize_transfer,build_manifest
class StorageTests(unittest.TestCase):
 def setUp(self)->None: self.profile=StorageProfile("s3","https://s3.example","lab","research/","keychain://lab")
 def test_manifest_preserves_scope_and_checksum(self)->None:
  manifest=build_manifest(self.profile,"research/raw.csv",b"raw", "import")
  self.assertEqual((manifest.bytes,manifest.sha256[:8]),(3,"d7439bee"))
  with self.assertRaises(ValueError): build_manifest(self.profile,"other/raw.csv",b"raw","import")
 def test_export_and_delete_require_approval(self)->None:
  for op in ("export","delete"):
   manifest=build_manifest(self.profile,"research/result",b"" if op=="delete" else b"data",op)
   with self.assertRaises(StorageApprovalRequired): authorize_transfer(manifest,False)
   authorize_transfer(manifest,True)
