# Deployment and CLI

During source development, run `python -m frontier_engine.cli doctor --json` for the host report and `python -m frontier_engine.cli status --json` for durable-store counts. `python -m frontier_engine.cli serve --json` starts authenticated `/status` and JSON-RPC 2.0 `/rpc` endpoints on a random `127.0.0.1` port and prints its ephemeral bearer token. Supported RPC methods are `system.doctor`, `runtime.probe`, `runtime.install`, `job.get`, `job.retry`, `agent.run`, `kernel.execute`, `kernel.restart`, and `kernel.status`; they return request-correlated structured results or errors. Annotation creation/listing and evidence review are available through the trusted desktop bridge and the corresponding CLI commands. `frontierctl serve --background`, `url`, `service-status`, `logs`, and `stop` manage a local child service without writing its bearer token to the state file or log. `FRONTIER_DATA_DIR` selects an explicit local data root.

`python -m frontier_engine.cli projects --json` lists local projects. Add `--name "Research workspace"` to create one durable project record.

`python -m frontier_engine.cli export --output C:\\path\\frontier.zip --json` writes a new ZIP snapshot of that local data root, including a SHA-256 manifest. It refuses to overwrite an archive or write inside the source root. `python -m frontier_engine.cli import --input C:\\path\\frontier.zip --destination C:\\path\\restored-data --json` requires a new or empty destination, verifies the manifest, and rejects traversal paths before writing data.

Before enabling a separately acquired runtime pack, verify its supplied manifest with `frontierctl verify-runtime-bundle --manifest PATH --bundle-root PATH`. The command returns `valid: true` only for the exact target platform, executable path, and SHA-256 recorded by the bundle publisher.

Desktop packages contain a separate `frontier-engine` sidecar produced in an isolated, pinned PyInstaller environment. Tauri places it next to the native application binary and installs its manifest plus Python and PyInstaller license texts under `runtime-packs/managed-engine`. Rust verifies protocol version, OS, architecture, a single-file relative path, and SHA-256 before every spawn. The `--managed-engine-smoke` native argument exercises this exact Rust-to-sidecar boundary without opening the window.

`.github/workflows/package.yml` builds MSI, DEB, AppImage, app, and DMG artifacts on their native hosts. macOS Apple silicon and Intel use separate runners because the managed sidecar is never cross-compiled. Package jobs run the sidecar doctor and the packaged Rust-boundary smoke before uploading artifacts.

Run `python scripts/release_gate.py` from a clean checkout before a release. It checks required repository files, acceptance-matrix coverage, smoke and package operating systems, the managed sidecar bundle contract, current lock-backed SBOM evidence, and a clean worktree. Use `--allow-dirty` only while iterating locally.

Daemon lifecycle, update verification, and remote tunnel support are not implemented yet. `serve --duration-seconds N` exists for controlled tests and demonstrations; the default service runs until interrupted.
