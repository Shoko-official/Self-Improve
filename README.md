# Shoko's LLM

Shoko's LLM is a local-first desktop AI and scientific workbench. Its internal Frontier engine provides the Tauri desktop shell with native host-capability reporting and a dependency-free local engine protocol.

## Development

```powershell
pnpm install
pnpm tauri dev
```

Engine protocol smoke test:

```powershell
$env:PYTHONPATH = 'engine'
python -m frontier_engine doctor
python -m frontier_engine.cli status --json
python -m frontier_engine.cli serve --json
python -m frontier_engine.cli serve --background --json
python -m frontier_engine.cli url --json
python -m frontier_engine.cli stop --json
python -m frontier_engine.cli projects --json
```

The initial Ollama runtime pack supports explicit local model installation and generation only after a live probe. Remote-provider credentials remain deliberately unavailable rather than emulated.

The Windows desktop launch was verified on 2026-08-15 with `pnpm tauri dev`. A functional unsigned Windows MSI with the managed engine is built with the debug Rust profile because host application control blocks an optimized Rust build script with `os error 4551`. This limitation is recorded in the acceptance matrix and is not represented as a signed release build.

Development IPC calls the source engine through `FRONTIER_PYTHON`. Packaged builds use a native PyInstaller sidecar, verify its target, path, protocol version, and SHA-256 before every process start, and never fall back to a global Python installation.

Build the managed sidecar, compliance inventory, and current Windows package:

```powershell
pnpm managed-engine
python scripts/generate_sbom.py
pnpm tauri build --debug --features managed-engine --config src-tauri\tauri.release.conf.json --bundles msi
```

GitHub Actions builds optimized native packages for Windows x64, Linux x64, macOS Apple silicon, and macOS Intel. These artifacts are unsigned unless signing credentials are explicitly configured.
