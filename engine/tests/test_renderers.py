import json
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

    def test_html_report_is_structural_and_inert(self) -> None:
        result = render_preview("text/html", '<h1>QC report</h1><p onclick="bad()">Ready <strong>now</strong></p><script>alert(1)</script><img src="https://example.test/x.png">')
        self.assertEqual(result["renderer_id"], "html.structural")
        self.assertIn("<h1>QC report</h1>", result["html"])
        self.assertIn("<strong>now</strong>", result["html"])
        self.assertNotIn("onclick", result["html"])
        self.assertNotIn("script", result["html"])
        self.assertNotIn("img", result["html"])
        self.assertEqual(result["resources"], "blocked")

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

    def test_scatter_figure_is_normalized_with_stable_point_selectors(self) -> None:
        content = json.dumps({"version": 1, "kind": "scatter", "title": "Cell embedding", "points": [{"id": "cell-1", "x": 1, "y": 2.5, "category": "Neuron"}]})
        result = render_preview("application/vnd.shokos.figure+json", content)
        self.assertEqual(result["renderer_id"], "figure.scatter")
        self.assertEqual(result["renderer_version"], "1")
        self.assertEqual(result["selector_schema"], {"kind": "point", "field": "id"})
        self.assertEqual(result["figure"]["points"][0]["id"], "cell-1")
        self.assertEqual(len(result["source_sha256"]), 64)
        self.assertEqual(result["execution"], "disabled")

    def test_matrix_and_sequence_figures_preserve_exact_selectors(self) -> None:
        matrix = render_preview("application/vnd.shokos.figure+json", json.dumps({"version": 1, "kind": "matrix", "title": "Markers", "rows": ["B cell"], "columns": ["CD79A"], "cells": [{"row": 0, "column": 0, "value": 0.8, "size": 0.6}]}))
        sequence = render_preview("application/vnd.shokos.figure+json", json.dumps({"version": 1, "kind": "sequence", "title": "KRAS", "length": 189, "features": [{"id": "domain-1", "start": 10, "end": 166, "label": "Ras domain"}]}))
        self.assertEqual(matrix["selector_schema"]["fields"], ["row", "column"])
        self.assertEqual(sequence["figure"]["features"][0]["end"], 166)
        self.assertEqual(sequence["selector_schema"], {"kind": "feature", "field": "id"})

    def test_figure_renderer_rejects_unbounded_and_invalid_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "FR-RENDERER-FIGURE-SCHEMA"):
            render_preview("application/vnd.shokos.figure+json", '{"version":1,"kind":"molecule"}')
        with self.assertRaisesRegex(ValueError, "FR-RENDERER-FIGURE-DUPLICATE-ID"):
            render_preview("application/vnd.shokos.figure+json", json.dumps({"version": 1, "kind": "scatter", "title": "Duplicate", "points": [{"id": "a", "x": 1, "y": 2}, {"id": "a", "x": 2, "y": 3}]}))
        with self.assertRaisesRegex(ValueError, "FR-RENDERER-FIGURE-NUMBER"):
            render_preview("application/vnd.shokos.figure+json", '{"version":1,"kind":"scatter","title":"Invalid","points":[{"id":"a","x":NaN,"y":2}]}')

    def test_tree_figure_preserves_node_selectors(self) -> None:
        preview = render_preview("application/vnd.shokos.figure+json", json.dumps({"version": 1, "kind": "tree", "title": "Phylogeny", "nodes": [{"id": "root", "label": "Root"}, {"id": "leaf", "parent_id": "root", "label": "Leaf"}]}))
        self.assertEqual(preview["renderer_id"], "figure.tree")
        self.assertEqual(preview["selector_schema"], {"kind": "node", "field": "id"})
        self.assertEqual(preview["figure"]["nodes"][1]["parent_id"], "root")

    def test_genome_figure_uses_bounded_feature_coordinates(self) -> None:
        preview = render_preview("application/vnd.shokos.figure+json", json.dumps({"version": 1, "kind": "genome", "title": "Locus", "length": 1200, "features": [{"id": "gene-a", "start": 120, "end": 840, "label": "GENE A"}]}))
        self.assertEqual(preview["renderer_id"], "figure.genome")
        self.assertEqual(preview["selector_schema"], {"kind": "feature", "field": "id"})
