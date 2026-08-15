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

    def test_notebook_preview_preserves_ids_outputs_and_does_not_execute(self) -> None:
        notebook = '{"nbformat":4,"cells":[{"id":"cell-a","cell_type":"code","execution_count":2,"source":["print(1)"],"outputs":[{"output_type":"stream","text":["1\\n"]}]}]}'
        result = render_preview("application/x-ipynb+json", notebook)
        self.assertEqual(result["renderer_id"], "notebook.structural")
        self.assertEqual(result["cells"][0]["id"], "cell-a")
        self.assertEqual(result["cells"][0]["output_types"], ["stream"])
        self.assertFalse(result["executed"])
        self.assertIn('data-cell-id="cell-a"', result["html"])

    def test_notebook_preview_rejects_malformed_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "FR-RENDERER-NOTEBOOK-INVALID-JSON"): render_preview("application/x-ipynb+json", "not json")
