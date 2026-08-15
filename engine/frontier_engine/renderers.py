"""Bounded, deterministic previews for local scientific artifact payloads."""

from __future__ import annotations

import csv
import hashlib
import html
import io
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
