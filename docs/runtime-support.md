# Runtime support

Runtime packs declare their protocol version, supported modalities, operations, formats, and health command. Frontier only enables an operation when the selected manifest supports the requested modality, operation, and model format.

The initial Ollama manifest is a local text and embedding adapter contract. Its probe reports a missing binary, unhealthy command, or empty model list as unavailable; it does not declare support from the vendor name alone.

The model registry can search the public Hugging Face model index and download one explicitly selected repository file. Transfers write to a temporary path, verify a supplied SHA-256 when available, then register the completed file. Downloading never changes `capability_state` from `unvalidated`.
