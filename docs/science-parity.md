# Frontier Science public-parity audit

Checked: 2026-08-21
Reference repository: `Shoko-official/Claude-Science-System-Prompts` at `a55a1709d36534d42462b51f61f9859bf4ab23b6` (locally inspected)  
Public documentation baseline: Claude Science overview, product page, and 2026-06-30 product announcement.

| Public behavior | Frontier status | Evidence |
| --- | --- | --- |
| Local desktop workbench | partially_verified | Tauri shell, local engine IPC, persistence and native package smoke are covered by `engine/tests/test_loopback.py`, `engine/tests/test_tauri_bundle.py`, and the package matrix. Full installed desktop UI end-to-end coverage remains pending. |
| Persistent Python/R kernels | partially_verified | Project-scoped persistent Python namespace, restart semantics, failed executions and explicit unavailable-R behavior are covered by `engine/tests/test_kernels.py` and `engine/tests/test_loopback.py`. Live GPU-backed or user-provisioned R environments are not claimed. |
| Versioned scientific artifacts and provenance | partially_verified | Append-only content-addressed versions, immutable preview source verification, independent provenance and local search are covered by `engine/tests/test_store.py` and `engine/tests/test_cli.py`. The desktop workspace renders the latest verified Markdown, structural HTML, tables, notebooks and supported scientific figures. |
| Annotation and reviewer workflows | partially_verified | Exact artifact-version targets, batch consumption and no-retarget behavior are covered by `engine/tests/test_annotations.py`; evidence-gap review is covered by `engine/tests/test_reviewer.py`. Reviewer findings do not claim a rerun or independent replication. |
| Local, SSH, cluster, and cloud compute | partially_verified | Local subprocess fixtures, approval-gated SSH and SLURM argument-vector plans, resource previews, terminal states and output retrieval records are covered by `engine/tests/test_compute.py`. Live external hosts and cloud credentials are not configured here. |
| Scientific renderers and connector packs | partially_verified | Bounded Markdown, HTML, table and notebook previews; typed MCP registry; and versioned scatter, matrix, sequence, tree and genome contracts have Python and frontend tests. Molecule, interactive 3D structure, PDF and publication renderers remain unavailable. |

This audit records public behavior only. It does not claim affiliation or compatibility with Anthropic or Claude Science.

The reference repository is Apache-2.0. Its prompts, scripts, and assets were inspected as implementation research only. No source text, scripts, schemas, or assets have been copied into Frontier in this slice.
