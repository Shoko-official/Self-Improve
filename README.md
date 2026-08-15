# Frontier

Frontier is a local-first desktop AI and scientific workbench. This repository currently contains the initial trust-boundary slice: a Tauri desktop shell, native host-capability reporting, and a dependency-free local-engine doctor protocol.

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

The initial Ollama runtime pack supports explicit local model installation and generation only after a live probe. Remote-provider credentials and scientific-kernel environments remain deliberately unavailable rather than emulated.

The Windows debug desktop launch was verified on 2026-08-15 with `pnpm tauri dev`. Release packaging remains blocked on this host by application control while a Rust release build script executes.

The desktop's development-engine IPC calls `python -m frontier_engine doctor` only in a debug build. Set `FRONTIER_PYTHON` to select the development interpreter. Release builds reject this IPC until Frontier bundles a managed Python runtime, so installed application behavior never relies on a global Python installation.
