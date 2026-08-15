# Acceptance matrix

| Area | Status | Evidence |
| --- | --- | --- |
| Desktop launch | partially_verified | Tauri configuration, icon, and native capability command compile under the Visual Studio developer environment |
| Engine protocol | verified | `python -m frontier_engine doctor` fixture |
| Hardware probe | partially_verified | Static OS, architecture, and core probe implemented |
| Local text runtime | not_verifiable_here | No runtime pack installed |
| Runtime packs | partially_verified | Versioned manifest validation, operation checks, and truthful local Ollama availability probes are covered by `engine/tests/test_runtimes.py` |
| Permissions | partially_verified | Exact resource/operation grants, one-time consumption, and revocation enforcement are covered by `engine/tests/test_permissions.py` |
| Python/R kernels | partially_verified | Persistent Python namespace, restart clearing, failed execution records, and honest R capability probing are covered by `engine/tests/test_kernels.py` |
| Reviewer | partially_verified | Evidence-gap findings for source, computed, and inference claims are covered by `engine/tests/test_reviewer.py`; no rerun claim is made |
| Annotations | partially_verified | Exact artifact-version targets, selectors, batch consumption, and no-retarget behavior are covered by `engine/tests/test_annotations.py` |
| Science remote compute | partially_verified | Local subprocess fixture and approval-gated remote plan contracts are covered by `engine/tests/test_compute.py`; no live remote host is claimed |
| Science cloud storage | partially_verified | Scoped S3/S3-compatible/GCS/Azure profile contracts, manifests, checksums, and write/delete approval gates are covered by `engine/tests/test_storage.py`; no live transfer is claimed |
| MCP | partially_verified | Stdio JSON-RPC initialize, typed tool discovery, structured read-only result, and unknown-tool rejection are covered by `engine/tests/test_mcp_server.py` |
| Remote providers | not_verifiable_here | No credential or provider configured |
| OpenAI-compatible/NIM provider contracts | partially_verified | Real HTTP health, model discovery, streaming, and explicit egress-approval contracts are covered by `engine/tests/test_providers.py` |
| Science parity | not_verifiable_here | Baseline matrix created |
| Windows package | not_verifiable_here | Tauri release build is blocked by the host application-control policy while executing a Rust build script: `os error 4551` |
| Science projects | partially_verified | SQLite project/session lifecycle, intra-project forks, session state, and archive write protection are covered by `engine/tests/test_store.py` |
| Scientific artifacts | partially_verified | Append-only versions, SHA-256 content storage, and independent provenance fields are covered by `engine/tests/test_store.py` |
| Jobs | partially_verified | Durable queue, claim, success/failure, and cooperative cancellation state transitions are covered by `engine/tests/test_store.py` |
| RAG | partially_verified | Durable ingestion, exact citations, lexical and injected-embedder hybrid contracts, and held-out source recall are covered by `engine/tests/test_rag.py` |
| Prompt compiler | partially_verified | Compact, standard, and extended variants have explicit budget checks in `engine/tests/test_prompts.py` |
