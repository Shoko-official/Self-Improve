# Multimodal attachments

Local attachments are inspected before use. Frontier records the resolved name, detected media type, modality family, byte count, and SHA-256, and rejects payloads above the configured bound. Inspection is local and does not upload data.

Adapters must disclose whether a target receives a native modality or a derived representation. For example, a 3D mesh sent to a vision target is explicitly planned as derived multiview images; Frontier never labels that as native 3D support. Unsupported adaptations fail with a stable diagnostic.
