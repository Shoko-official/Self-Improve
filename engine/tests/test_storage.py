import tempfile
import unittest
from pathlib import Path
from frontier_engine.storage import StorageApprovalRequired,StorageProfile,authorize_transfer,build_manifest,execute_local_transfer
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

 def test_local_export_import_and_delete_verify_integrity(self)->None:
  with tempfile.TemporaryDirectory() as directory:
   profile=StorageProfile("s3_compatible",Path(directory).as_uri(),"local","research/","fixture://credential")
   export=build_manifest(profile,"research/result.txt",b"result","export")
   with self.assertRaises(StorageApprovalRequired): execute_local_transfer(export,False)
   self.assertEqual(execute_local_transfer(export,True)["sha256"],export.sha256)
   imported=build_manifest(profile,"research/result.txt",b"result","import")
   self.assertEqual(execute_local_transfer(imported,True)["content"],b"result")
   deleted=build_manifest(profile,"research/result.txt",b"","delete")
   self.assertEqual(execute_local_transfer(deleted,True)["state"],"succeeded")

 def test_local_transfer_rejects_corrupt_objects_and_non_file_endpoints(self)->None:
  with tempfile.TemporaryDirectory() as directory:
   profile=StorageProfile("s3_compatible",Path(directory).as_uri(),"local","research/","fixture://credential")
   export=build_manifest(profile,"research/result.txt",b"result","export"); execute_local_transfer(export,True)
   Path(directory,"research","result.txt").write_bytes(b"tampered")
   with self.assertRaisesRegex(ValueError,"FR-STORAGE-INTEGRITY"): execute_local_transfer(build_manifest(profile,"research/result.txt",b"result","import"),True)
  remote=StorageProfile("s3","https://example","lab","research/","keychain://lab")
  with self.assertRaisesRegex(ValueError,"FR-STORAGE-ENDPOINT"): execute_local_transfer(build_manifest(remote,"research/result",b"data","export"),True)
