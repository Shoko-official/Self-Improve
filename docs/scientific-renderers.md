# Scientific renderers

Frontier currently exposes bounded local previews for Markdown/plain text, escaped HTML, and CSV/TSV tables through `frontierctl render-preview` and the trusted desktop bridge. Every preview records the source SHA-256, renderer identifier/version, and structural table row/column selectors. Payloads larger than 1 MiB are rejected before parsing; HTML is displayed as escaped source with execution disabled.

Molecular, sequence/tree, genomic, notebook, PDF, and publication export renderers remain planned. They must be added with representative fixtures, malformed/large-file tests, accessibility checks, and structural or pixel assertions before being marked verified.
