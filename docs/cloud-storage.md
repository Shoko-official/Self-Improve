# Cloud storage

Profiles define a storage type, endpoint, exact container, prefix, and a credential handle only. Secrets are not embedded in profiles. Transfer manifests retain object key, bytes, checksum, operation, and egress estimate. Export and delete require explicit approval; paths outside the granted prefix are rejected.

The local fixture adapter accepts a `file://` endpoint and executes approved export/delete or integrity-checked import operations atomically, without credentials or network access. The same boundary is available through `frontierctl storage-transfer` and the trusted desktop bridge. It is useful for deterministic tests of transfer state and checksums. It does not claim live S3, GCS, or Azure transfers.
