# Literature and evidence

Every retrieved chunk stores the source URI, source label, source hash, exact text, and byte offsets. Retrieval has two explicit modes: lexical when no embedding adapter is installed, and hybrid only when a caller supplies an embedding implementation.

Evaluation is a held-out query-to-source contract. It reports the number of cases, source-level hits, and recall at `k`; it does not claim factual validation of source content.
