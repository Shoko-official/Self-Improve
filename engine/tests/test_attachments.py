import tempfile
import unittest
from pathlib import Path

from frontier_engine.attachments import inspect_attachment, plan_adaptation


class AttachmentTests(unittest.TestCase):
    def test_inspection_is_bounded_and_hashes_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.png"
            path.write_bytes(b"fixture")
            descriptor = inspect_attachment(path)
            self.assertEqual((descriptor.kind, descriptor.bytes, len(descriptor.sha256)), ("image", 7, 64))
            with self.assertRaisesRegex(ValueError, "FR-ATTACHMENT-TOO-LARGE"):
                inspect_attachment(path, max_bytes=1)

    def test_three_d_adaptation_discloses_derived_representation(self) -> None:
        plan = plan_adaptation("model/obj", "vision")
        self.assertEqual(plan.mode, "derived_multiview")
        self.assertIn("derived multiview", plan.disclosure)

    def test_unsupported_adaptation_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "FR-ATTACHMENT-ADAPTATION-UNSUPPORTED"):
            plan_adaptation("application/pdf", "vision")
