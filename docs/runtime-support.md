# Runtime support

Runtime packs declare their protocol version, supported modalities, operations, formats, and health command. Frontier only enables an operation when the selected manifest supports the requested modality, operation, and model format.

The initial Ollama manifest is a local text and embedding adapter contract. Its probe reports a missing binary, unhealthy command, or empty model list as unavailable; it does not declare support from the vendor name alone.

`frontierctl install-ollama-model --project-id ID --model MODEL` is an explicit local `ollama pull MODEL` operation. It records pull output as durable job events and only succeeds after a fresh probe lists that exact model. A missing or unhealthy executable, a failed pull, or a mismatched post-pull probe remains a failed job with its diagnostic; it never substitutes a model or remote provider.

The desktop Models surface exposes this same operation through development-only IPC. It requires a project ID and exact model identifier, then renders the returned job events and diagnostic. Packaged builds continue to reject development-engine IPC until Frontier bundles a managed engine runtime.

Managed bundles use a JSON manifest with runtime/version, protocol version, target platform and architecture, executable-relative path, and SHA-256. `frontierctl verify-runtime-bundle --manifest PATH --bundle-root PATH` checks platform, path containment, file presence, and exact bytes. A missing or mismatched bundle is reported with a stable `FR-BUNDLE-*` diagnostic; verification never falls back to a host runtime.

The model registry can search the public Hugging Face model index and download one explicitly selected repository file. Transfers write to a temporary path, verify a supplied SHA-256 when available, then register the completed file. Downloading never changes `capability_state` from `unvalidated`.
