# Acceptance matrix

| Area | Status | Evidence |
| --- | --- | --- |
| Desktop launch | verified | `pnpm tauri dev` compiled `target\\debug\\frontier.exe` through the Visual Studio developer environment and launched it on 2026-08-15 |
| Engine protocol | partially_verified | `python -m frontier_engine doctor` fixture plus debug-only desktop IPC; release correctly refuses the call until a managed Python runtime is bundled |
| Local control plane | partially_verified | `frontierctl serve` starts an authenticated ephemeral-bearer status endpoint bound to `127.0.0.1`; daemon lifecycle, tunnels, and updates remain unimplemented |
| Hardware probe | partially_verified | Static OS, architecture, and core probe implemented |
| Local text runtime | not_verifiable_here | No runtime pack installed |
| Runtime packs | partially_verified | Versioned manifest validation, operation checks, and truthful local Ollama availability probes are covered by `engine/tests/test_runtimes.py` |
| Permissions | partially_verified | Exact resource/operation grants, one-time consumption, and revocation enforcement are covered by `engine/tests/test_permissions.py` |
| Python/R kernels | partially_verified | Persistent Python namespace, restart clearing, failed execution records, and honest R capability probing are covered by `engine/tests/test_kernels.py` |
| Reviewer | partially_verified | Evidence-gap findings for source, computed, and inference claims are covered by `engine/tests/test_reviewer.py`; no rerun claim is made |
| Annotations | partially_verified | Exact artifact-version targets, selectors, batch consumption, and no-retarget behavior are covered by `engine/tests/test_annotations.py` |
| Science remote compute | partially_verified | Local subprocess fixture and approval-gated remote plan contracts are covered by `engine/tests/test_compute.py`; no live remote host is claimed |
| Science cloud storage | partially_verified | Scoped S3/S3-compatible/GCS/Azure profile contracts, manifests, checksums, and write/delete approval gates are covered by `engine/tests/test_storage.py`; no live transfer is claimed |
| Local data transfer | partially_verified | `frontierctl` ZIP export/import writes a SHA-256 manifest, requires an explicit empty import target, and rejects traversal paths in `engine/tests/test_cli.py` |
| MCP | partially_verified | Stdio JSON-RPC initialize, typed tool discovery, structured read-only result, and unknown-tool rejection are covered by `engine/tests/test_mcp_server.py` |
| Agent | partially_verified | Project-scoped plans, todo transitions, memory search, and deletion are covered by `engine/tests/test_agent_state.py` |
| Diagnostics | partially_verified | Stable codes, evidence/fact separation, confidence-bounded inferences, and redaction are covered by `engine/tests/test_diagnostics.py` |
| Benchmark | partially_verified | Raw samples, required environment fingerprints, summary metrics, and comparison deltas are covered by `engine/tests/test_benchmarks.py` |
| Automation | partially_verified | Durable definitions, dry-run history, and external-effect approval gates are covered by `engine/tests/test_automations.py` |
| Operational UX | partially_verified | Durable lock-screen-safe notification records, deep links, and acknowledgement states are covered by `engine/tests/test_notifications.py` |
| Remote providers | not_verifiable_here | No credential or provider configured |
| OpenAI-compatible/NIM provider contracts | partially_verified | Real HTTP health, model discovery, streaming, and explicit egress-approval contracts are covered by `engine/tests/test_providers.py` |
| Science parity | not_verifiable_here | Baseline matrix created |
| Windows package | not_verifiable_here | Tauri release build is blocked by the host application-control policy while executing a Rust build script: `os error 4551` |
| Science projects | partially_verified | SQLite project/session lifecycle, intra-project forks, session state, and archive write protection are covered by `engine/tests/test_store.py`; the desktop workspaces view lists and creates project records through debug-only IPC |
| Scientific artifacts | partially_verified | Append-only versions, SHA-256 content storage, and independent provenance fields are covered by `engine/tests/test_store.py` |
| Jobs | partially_verified | Durable queue, claim, success/failure, and cooperative cancellation state transitions are covered by `engine/tests/test_store.py` |
| RAG | partially_verified | Durable ingestion, exact citations, lexical and injected-embedder hybrid contracts, and held-out source recall are covered by `engine/tests/test_rag.py` |
| Scientific claims | partially_verified | Typed claims preserve uncertainty, lifecycle status, and exact evidence URI/selector links in `engine/tests/test_claims.py`; the desktop Science workspace creates, lists, and updates local claims through debug-only IPC |
| Prompt compiler | partially_verified | Compact, standard, and extended variants have explicit budget checks in `engine/tests/test_prompts.py` |
