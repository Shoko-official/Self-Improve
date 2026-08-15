# Cloud storage

Profiles define a storage type, endpoint, exact container, prefix, and a credential handle only. Secrets are not embedded in profiles. Transfer manifests retain object key, bytes, checksum, operation, and egress estimate. Export and delete require explicit approval; paths outside the granted prefix are rejected.

This slice validates storage contracts and fixtures only. It does not claim live S3, GCS, or Azure transfers.
