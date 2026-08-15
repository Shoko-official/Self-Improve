# Cloud storage

Profiles define a storage type, endpoint, exact container, prefix, and a credential handle only. Secrets are not embedded in profiles. Transfer manifests retain object key, bytes, checksum, operation, and egress estimate. Export and delete require explicit approval; paths outside the granted prefix are rejected.

`probe_remote_storage` performs a bounded, read-only HTTP HEAD against a configured remote endpoint after explicit approval. HTTP 401/403 is reported as reachable with `authentication_required: true`; network failures return `FR-STORAGE-PROBE-FAILED`. This probe does not claim object listing or mutation support.

`execute_presigned_transfer` supports import, export, and delete through a caller-supplied signed query URL. It requires explicit approval for export/delete, rejects embedded credentials and host mismatches, verifies imported bytes against the manifest, and never persists or derives credentials. Provider SDK signing and object listing remain separate capability work.

`list_presigned_objects` adds bounded read-only listing through a signed query URL. It accepts common S3/GCS/Azure-compatible JSON or XML listings, filters to the granted prefix, normalizes key/size/etag metadata, and requires explicit approval. It does not claim provider SDK authentication or pagination beyond the supplied signed response.

The local fixture adapter accepts a `file://` endpoint and executes approved export/delete or integrity-checked import operations atomically, without credentials or network access. The same boundary is available through `frontierctl storage-transfer` and the trusted desktop bridge. It is useful for deterministic tests of transfer state and checksums. It does not claim live S3, GCS, or Azure transfers.
