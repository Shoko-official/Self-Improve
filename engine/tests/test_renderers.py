import unittest

from frontier_engine.renderers import render_preview


class RendererTests(unittest.TestCase):
    def test_markdown_preview_is_escaped_and_hashed(self) -> None:
        result = render_preview("text/markdown", "# Result\n\n<script>alert(1)</script>")
        self.assertEqual(result["renderer_id"], "markdown.basic")
        self.assertEqual(len(result["source_sha256"]), 64)
        self.assertIn("&lt;script&gt;", result["html"])

    def test_table_preview_preserves_row_and_column_identity(self) -> None:
        result = render_preview("text/csv", "name,value\nalpha,1\nbeta,2")
        self.assertEqual(result["renderer_id"], "table.delimited")
        self.assertEqual(result["rows"], 2)
        self.assertIn('data-row-index="1"', result["html"])
        self.assertIn('data-column-index="1"', result["html"])

    def test_preview_rejects_unsupported_and_oversized_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "FR-RENDERER-UNSUPPORTED-MEDIA"): render_preview("application/pdf", "fixture")
        with self.assertRaisesRegex(ValueError, "FR-RENDERER-PAYLOAD-TOO-LARGE"): render_preview("text/plain", "large", 2)
