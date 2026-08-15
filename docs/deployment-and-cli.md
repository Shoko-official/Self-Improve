# Deployment and CLI

During development, run `python -m frontier_engine.cli doctor --json` for the host report and `python -m frontier_engine.cli status --json` for durable-store counts. `FRONTIER_DATA_DIR` selects an explicit local data root.

`python -m frontier_engine.cli projects --json` lists local projects. Add `--name "Research workspace"` to create one durable project record.

`python -m frontier_engine.cli export --output C:\\path\\frontier.zip --json` writes a new ZIP snapshot of that local data root, including a SHA-256 manifest. It refuses to overwrite an archive or write inside the source root. `python -m frontier_engine.cli import --input C:\\path\\frontier.zip --destination C:\\path\\restored-data --json` requires a new or empty destination, verifies the manifest, and rejects traversal paths before writing data.

The remaining deployment commands, authenticated loopback serving, update verification, and remote tunnel support are not implemented yet.
