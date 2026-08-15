# Deployment and CLI

During development, run `python -m frontier_engine.cli doctor --json` for the host report and `python -m frontier_engine.cli status --json` for durable-store counts. `python -m frontier_engine.cli serve --json` starts an authenticated status endpoint on a random `127.0.0.1` port and prints its ephemeral bearer token. `frontierctl serve --background`, `url`, `service-status`, `logs`, and `stop` manage a local child service without writing its bearer token to the state file or log. `FRONTIER_DATA_DIR` selects an explicit local data root.

`python -m frontier_engine.cli projects --json` lists local projects. Add `--name "Research workspace"` to create one durable project record.

`python -m frontier_engine.cli export --output C:\\path\\frontier.zip --json` writes a new ZIP snapshot of that local data root, including a SHA-256 manifest. It refuses to overwrite an archive or write inside the source root. `python -m frontier_engine.cli import --input C:\\path\\frontier.zip --destination C:\\path\\restored-data --json` requires a new or empty destination, verifies the manifest, and rejects traversal paths before writing data.

Daemon lifecycle, update verification, and remote tunnel support are not implemented yet. `serve --duration-seconds N` exists for controlled tests and demonstrations; the default service runs until interrupted.
