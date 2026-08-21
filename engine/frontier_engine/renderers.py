"""Bounded, deterministic previews for local scientific artifact payloads."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
import re

MAX_PREVIEW_BYTES = 1_000_000


def render_preview(media_type: str, content: str, max_bytes: int = MAX_PREVIEW_BYTES) -> dict[str, object]:
    payload = content.encode("utf-8")
    if len(payload) > max_bytes: raise ValueError("FR-RENDERER-PAYLOAD-TOO-LARGE")
    digest = hashlib.sha256(payload).hexdigest()
    if media_type in {"text/markdown", "text/plain"}: renderer, version, markup, metadata = "markdown.basic", "1", _markdown(content), {}
    elif media_type == "text/html": renderer, version, markup, metadata = "html.sandboxed", "1", f"<pre>{html.escape(content)}</pre>", {"execution": "disabled"}
    elif media_type in {"text/csv", "text/tab-separated-values"}:
        markup, metadata = _table(content, "\t" if media_type.endswith("tab-separated-values") else ",")
        renderer, version = "table.delimited", "1"
    elif media_type == "application/x-ipynb+json":
        markup, metadata = _notebook(content)
        renderer, version = "notebook.structural", "1"
    elif media_type == "application/vnd.shokos.figure+json":
        metadata = _scientific_figure(content)
        markup, renderer, version = "", f"figure.{metadata['figure']['kind']}", "1"
    else: raise ValueError("FR-RENDERER-UNSUPPORTED-MEDIA")
    return {"renderer_id": renderer, "renderer_version": version, "source_sha256": digest, "html": markup, **metadata}


def _markdown(content: str) -> str:
    escaped = html.escape(content)
    escaped = re.sub(r"^### (.+)$", r"<h3>\1</h3>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"^## (.+)$", r"<h2>\1</h2>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"^# (.+)$", r"<h1>\1</h1>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"```(?:[A-Za-z0-9_+-]+)?\n(.*?)```", r"<pre><code>\1</code></pre>", escaped, flags=re.DOTALL)
    blocks = [block.strip() for block in escaped.split("\n\n") if block.strip()]
    return "".join(block if block.startswith("<h") or block.startswith("<pre>") else f"<p>{block.replace(chr(10), '<br>')}</p>" for block in blocks)


def _table(content: str, delimiter: str) -> tuple[str, dict[str, object]]:
    rows = list(csv.reader(io.StringIO(content), delimiter=delimiter))
    if not rows: return "<table></table>", {"rows": [], "warnings": ["empty table"]}
    columns = rows[0]
    body = rows[1:]
    warnings = []
    if any(len(row) != len(columns) for row in body): warnings.append("ragged rows padded with empty cells")
    header = "".join(f"<th data-column-index=\"{index}\">{html.escape(value)}</th>" for index, value in enumerate(columns))
    rendered = []
    for row_index, row in enumerate(body):
        cells = row + [""] * max(0, len(columns) - len(row))
        rendered.append(f"<tr data-row-index=\"{row_index}\">" + "".join(f"<td data-column-index=\"{index}\">{html.escape(value)}</td>" for index, value in enumerate(cells[:len(columns)])) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rendered)}</tbody></table>", {"rows": len(body), "columns": len(columns), "warnings": warnings}


def _notebook(content: str) -> tuple[str, dict[str, object]]:
    try: notebook = json.loads(content)
    except json.JSONDecodeError as error: raise ValueError("FR-RENDERER-NOTEBOOK-INVALID-JSON") from error
    if not isinstance(notebook, dict) or not isinstance(notebook.get("cells"), list): raise ValueError("FR-RENDERER-NOTEBOOK-SCHEMA")
    cells = []; blocks = []; warnings = []
    for index, cell in enumerate(notebook["cells"]):
        if not isinstance(cell, dict) or cell.get("cell_type") not in {"code", "markdown", "raw"}: raise ValueError("FR-RENDERER-NOTEBOOK-CELL-SCHEMA")
        cell_id = str(cell.get("id") or f"missing-{index}")
        if "id" not in cell: warnings.append(f"cell {index} has no id")
        source = cell.get("source", "")
        source_text = "".join(source) if isinstance(source, list) else str(source)
        outputs = cell.get("outputs", []) if cell["cell_type"] == "code" else []
        if not isinstance(outputs, list): raise ValueError("FR-RENDERER-NOTEBOOK-OUTPUT-SCHEMA")
        output_types = [str(output.get("output_type", "unknown")) for output in outputs if isinstance(output, dict)]
        cells.append({"id": cell_id, "cell_type": cell["cell_type"], "execution_count": cell.get("execution_count"), "output_types": output_types, "metadata": cell.get("metadata", {})})
        block = f"<section data-cell-id=\"{html.escape(cell_id)}\" data-cell-index=\"{index}\"><div class=\"cell-meta\">{html.escape(cell['cell_type'])} · {html.escape(str(cell.get('execution_count') or 'not executed'))}</div><pre>{html.escape(source_text)}</pre>"
        for output in outputs:
            if not isinstance(output, dict): continue
            summary = output.get("text", output.get("ename", output.get("output_type", "output")))
            text = "".join(summary) if isinstance(summary, list) else str(summary)
            block += f"<pre data-output-type=\"{html.escape(str(output.get('output_type', 'unknown')))}\">{html.escape(text)}</pre>"
        blocks.append(block + "</section>")
    return "".join(blocks), {"cells": cells, "warnings": warnings, "executed": False}


def _scientific_figure(content: str) -> dict[str, object]:
    try: raw = json.loads(content)
    except json.JSONDecodeError as error: raise ValueError("FR-RENDERER-FIGURE-INVALID-JSON") from error
    if not isinstance(raw, dict) or raw.get("version") != 1 or raw.get("kind") not in {"scatter", "matrix", "sequence", "tree", "genome"}:
        raise ValueError("FR-RENDERER-FIGURE-SCHEMA")
    figure = {
        "version": 1,
        "kind": raw["kind"],
        "title": _bounded_text(raw.get("title"), "title", 160),
        "subtitle": _bounded_text(raw.get("subtitle", ""), "subtitle", 240, required=False),
    }
    if raw["kind"] == "scatter":
        figure.update(_scatter_figure(raw))
        selector = {"kind": "point", "field": "id"}
    elif raw["kind"] == "matrix":
        figure.update(_matrix_figure(raw))
        selector = {"kind": "cell", "fields": ["row", "column"]}
    elif raw["kind"] == "sequence":
        figure.update(_sequence_figure(raw))
        selector = {"kind": "feature", "field": "id"}
    elif raw["kind"] == "tree":
        figure.update(_tree_figure(raw))
        selector = {"kind": "node", "field": "id"}
    else:
        figure.update(_sequence_figure(raw))
        selector = {"kind": "feature", "field": "id"}
    return {"figure": figure, "warnings": [], "selector_schema": selector, "execution": "disabled"}


def _scatter_figure(raw: dict[str, object]) -> dict[str, object]:
    points = raw.get("points")
    if not isinstance(points, list) or not points or len(points) > 5_000:
        raise ValueError("FR-RENDERER-FIGURE-POINTS")
    normalized = []
    identifiers = set()
    for index, point in enumerate(points):
        if not isinstance(point, dict): raise ValueError("FR-RENDERER-FIGURE-POINT")
        identifier = _bounded_text(point.get("id"), f"points[{index}].id", 80)
        if identifier in identifiers: raise ValueError("FR-RENDERER-FIGURE-DUPLICATE-ID")
        identifiers.add(identifier)
        normalized.append({
            "id": identifier,
            "x": _finite_number(point.get("x")),
            "y": _finite_number(point.get("y")),
            "category": _bounded_text(point.get("category", "Uncategorized"), f"points[{index}].category", 60),
            "label": _bounded_text(point.get("label", identifier), f"points[{index}].label", 120),
        })
    return {
        "x_label": _bounded_text(raw.get("x_label", "Dimension 1"), "x_label", 80),
        "y_label": _bounded_text(raw.get("y_label", "Dimension 2"), "y_label", 80),
        "points": normalized,
    }


def _matrix_figure(raw: dict[str, object]) -> dict[str, object]:
    rows = _label_axis(raw.get("rows"), "rows")
    columns = _label_axis(raw.get("columns"), "columns")
    cells = raw.get("cells")
    if not isinstance(cells, list) or not cells or len(cells) > 10_000:
        raise ValueError("FR-RENDERER-FIGURE-CELLS")
    normalized = []
    occupied = set()
    for cell in cells:
        if not isinstance(cell, dict) or not isinstance(cell.get("row"), int) or not isinstance(cell.get("column"), int):
            raise ValueError("FR-RENDERER-FIGURE-CELL")
        row, column = cell["row"], cell["column"]
        if row < 0 or row >= len(rows) or column < 0 or column >= len(columns) or (row, column) in occupied:
            raise ValueError("FR-RENDERER-FIGURE-CELL")
        occupied.add((row, column))
        size = _finite_number(cell.get("size", 1))
        if size < 0: raise ValueError("FR-RENDERER-FIGURE-CELL-SIZE")
        normalized.append({"row": row, "column": column, "value": _finite_number(cell.get("value")), "size": size})
    return {"rows": rows, "columns": columns, "cells": normalized}


def _sequence_figure(raw: dict[str, object]) -> dict[str, object]:
    length = raw.get("length")
    features = raw.get("features")
    if not isinstance(length, int) or isinstance(length, bool) or length < 1 or length > 10_000_000:
        raise ValueError("FR-RENDERER-FIGURE-SEQUENCE-LENGTH")
    if not isinstance(features, list) or not features or len(features) > 1_000:
        raise ValueError("FR-RENDERER-FIGURE-FEATURES")
    normalized = []
    identifiers = set()
    for index, feature in enumerate(features):
        if not isinstance(feature, dict): raise ValueError("FR-RENDERER-FIGURE-FEATURE")
        identifier = _bounded_text(feature.get("id"), f"features[{index}].id", 80)
        start, end = feature.get("start"), feature.get("end")
        if identifier in identifiers or not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or start < 1 or end < start or end > length:
            raise ValueError("FR-RENDERER-FIGURE-FEATURE")
        identifiers.add(identifier)
        normalized.append({
            "id": identifier,
            "start": start,
            "end": end,
            "label": _bounded_text(feature.get("label", identifier), f"features[{index}].label", 120),
            "category": _bounded_text(feature.get("category", "Feature"), f"features[{index}].category", 60),
        })
    return {"length": length, "features": normalized}


def _tree_figure(raw: dict[str, object]) -> dict[str, object]:
    nodes = raw.get("nodes")
    if not isinstance(nodes, list) or not nodes or len(nodes) > 1_000:
        raise ValueError("FR-RENDERER-FIGURE-TREE-NODES")
    normalized = []
    identifiers = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict): raise ValueError("FR-RENDERER-FIGURE-TREE-NODE")
        identifier = _bounded_text(node.get("id"), f"nodes[{index}].id", 80)
        parent = node.get("parent_id")
        if identifier in identifiers or parent is not None and not isinstance(parent, str): raise ValueError("FR-RENDERER-FIGURE-TREE-NODE")
        identifiers.add(identifier)
        normalized.append({"id": identifier, "parent_id": parent, "label": _bounded_text(node.get("label", identifier), f"nodes[{index}].label", 120), "category": _bounded_text(node.get("category", "Node"), f"nodes[{index}].category", 60)})
    if sum(node["parent_id"] is None for node in normalized) != 1 or any(node["parent_id"] is not None and node["parent_id"] not in identifiers for node in normalized): raise ValueError("FR-RENDERER-FIGURE-TREE-TOPOLOGY")
    return {"nodes": normalized}


def _label_axis(raw: object, field: str) -> list[str]:
    if not isinstance(raw, list) or not raw or len(raw) > 100:
        raise ValueError(f"FR-RENDERER-FIGURE-{field.upper()}")
    labels = [_bounded_text(value, field, 80) for value in raw]
    if len(set(labels)) != len(labels): raise ValueError(f"FR-RENDERER-FIGURE-{field.upper()}-DUPLICATE")
    return labels


def _bounded_text(raw: object, field: str, limit: int, required: bool = True) -> str:
    if not isinstance(raw, str): raise ValueError(f"FR-RENDERER-FIGURE-TEXT:{field}")
    value = raw.strip()
    if (required and not value) or len(value) > limit: raise ValueError(f"FR-RENDERER-FIGURE-TEXT:{field}")
    return value


def _finite_number(raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        raise ValueError("FR-RENDERER-FIGURE-NUMBER")
    return float(raw)
