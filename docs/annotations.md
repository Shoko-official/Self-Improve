# Annotations

Annotations carry an exact artifact-version identifier, target type, structured selector, and body. They are never retargeted to a newer version. Open annotations can be consumed as a batch for a subsequent message; consumed records remain durable.

`frontierctl annotations --artifact-version-id ID` lists open records. Supplying `--target-kind`, JSON `--selector`, and `--body` creates one after validating the immutable version exists. `frontierctl consume-annotations --annotation-id ID` consumes a batch once. The desktop Artefacts surface uses the same validation boundary.
