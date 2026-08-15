# Deployment and CLI

During development, run `python -m frontier_engine.cli doctor --json` for the host report and `python -m frontier_engine.cli status --json` for durable-store counts. `FRONTIER_DATA_DIR` selects an explicit local data root.

The remaining deployment commands, authenticated loopback serving, update verification, import/export, and remote tunnel support are not implemented yet.
