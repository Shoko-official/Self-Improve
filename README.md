# Frontier

Frontier is a local-first desktop AI and scientific workbench. This repository currently contains the initial trust-boundary slice: a Tauri desktop shell, a native host-capability command, and a dependency-free local-engine doctor protocol.

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
```

The project does not yet include a model runtime pack, remote-provider credential, or scientific-kernel environment. These absent capabilities are deliberately reported as unavailable rather than emulated.
