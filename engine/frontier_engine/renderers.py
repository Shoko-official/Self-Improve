"""Bounded, deterministic previews for local scientific artifact payloads."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
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
