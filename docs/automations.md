# Automations

Automation definitions, typed steps, attempts, outputs, diagnostics, and run history are durable in the local automation ledger. Pipelines are validated as directed acyclic graphs before persistence. Each step declares dependencies and zero to five retries.

The executable step catalog is generated from real handlers. It currently contains local Ollama model generation, evidence review, artifact provenance, a reproducible Python kernel, local literature and artifact reads, and public Hugging Face model search. Unknown skills and unimplemented connectors are rejected and do not appear in the desktop editor.

Runs default to dry-run and record a simulated terminal state without invoking a model, skill, connector, or network. Execute mode runs in a separate worker, supports cooperative cancellation, and retains each attempt. Failed or cancelled runs can be retried with an exact parent-run link.

Manual and bounded interval schedules are supported. While the desktop is open it checks due schedules every 30 seconds. A due pipeline with only local effects starts in its own worker. A due pipeline containing the public network connector remains pending for explicit approval.

External effects cannot execute unless the user approves that individual run. Approval is recorded with the run and is never inferred from a previous execution.
