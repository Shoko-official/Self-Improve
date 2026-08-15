# Scientific renderers

Frontier currently exposes bounded local previews for Markdown/plain text, escaped HTML, CSV/TSV tables, and structural `.ipynb` notebooks through `frontierctl render-preview` and the trusted desktop bridge. Every preview records the source SHA-256 and renderer identifier/version. Tables preserve row/column selectors; notebooks preserve cell IDs, execution counts, metadata, outputs, and execution-disabled state. Payloads larger than 1 MiB are rejected before parsing; HTML is displayed as escaped source with execution disabled.

Molecular, sequence/tree, genomic, PDF, and publication export renderers remain planned. They must be added with representative fixtures, malformed/large-file tests, accessibility checks, and structural or pixel assertions before being marked verified.
