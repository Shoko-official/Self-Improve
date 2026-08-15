# Threat model outline

## Assets

Projects, artifacts, model credentials, local files, scientific inputs, execution records, and remote-compute configurations are sensitive assets.

## Boundaries

The webview has no direct unrestricted filesystem, shell, secret, or network access. Native commands and engine actions are explicit IPC endpoints. Any external provider, storage, or compute action must carry a scoped, durable approval record.

## Initial controls

Provider fallbacks are forbidden, runtime packs are versioned and checksum-verified, remote-code model execution is disabled by default, and diagnostic events must not contain source text or credentials.
