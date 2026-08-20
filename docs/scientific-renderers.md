# Scientific renderers

Frontier exposes bounded local previews for Markdown/plain text, escaped HTML, CSV/TSV tables, structural `.ipynb` notebooks, and Shoko scientific figure JSON through `frontierctl render-preview` and the trusted desktop bridge. Every preview records the source SHA-256 and renderer identifier/version. Tables preserve row/column selectors; notebooks preserve cell IDs, execution counts, metadata, outputs, and execution-disabled state. Payloads larger than 1 MiB are rejected before parsing; HTML is displayed as escaped source with execution disabled.

## Scientific figure contract

`application/vnd.shokos.figure+json` version 1 supports three non-executing figure kinds:

- `scatter` accepts at most 5,000 finite two-dimensional points with unique IDs, bounded labels, categories, and exact point selectors.
- `matrix` accepts at most 100 row labels, 100 column labels, and 10,000 finite quantitative cells with exact row and column selectors.
- `sequence` accepts a bounded sequence length and at most 1,000 coordinate-checked features with unique IDs and exact feature selectors.

The engine validates and normalizes the JSON. The desktop renders only the returned structure as React-owned SVG, so source JSON cannot provide markup or executable content. Figure creation, preview, selector inspection, and versioned artifact save are available in the Science workbench. The initial JSON shown in the editor is explicitly an editable template, not measured scientific data.

Molecular, three-dimensional structure, phylogenetic tree, genomic, PDF, and publication export renderers remain unavailable. They must be added with representative fixtures, malformed and large-file tests, accessibility checks, and structural or pixel assertions before being shown in the product.
