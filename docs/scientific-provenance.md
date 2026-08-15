# Scientific provenance

Frontier treats the execution log as authoritative evidence, not generated code or a reviewer label. Every artifact version stores independent fields for messages, code, execution log, environment, inputs, and review. Payloads use SHA-256 content addressing and version records are append-only.

Archived projects remain durable and readable while rejecting new sessions, artifacts, and versions. A session fork may only point to a session in the same project.
