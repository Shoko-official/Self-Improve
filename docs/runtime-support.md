# Runtime support

Runtime packs declare their protocol version, supported modalities, operations, formats, and health command. Frontier only enables an operation when the selected manifest supports the requested modality, operation, and model format.

The initial Ollama manifest is a local text and embedding adapter contract. Its probe reports a missing binary, unhealthy command, or empty model list as unavailable; it does not declare support from the vendor name alone.

`frontierctl install-ollama-model --project-id ID --model MODEL` is an explicit local `ollama pull MODEL` operation. It records pull output as durable job events and only succeeds after a fresh probe lists that exact model. A missing or unhealthy executable, a failed pull, or a mismatched post-pull probe remains a failed job with its diagnostic; it never substitutes a model or remote provider.

The desktop Models surface exposes this same operation through development-only IPC. It requires a project ID and exact model identifier, then renders the returned job events and diagnostic. Packaged builds continue to reject development-engine IPC until Frontier bundles a managed engine runtime.

Managed bundles use a JSON manifest with runtime/version, protocol version, target platform and architecture, executable-relative path, and SHA-256. `frontierctl verify-runtime-bundle --manifest PATH --bundle-root PATH` checks platform, path containment, file presence, and exact bytes. A missing or mismatched bundle is reported with a stable `FR-BUNDLE-*` diagnostic; verification never falls back to a host runtime.

Tauri packages the `runtime-packs` manifest directory as a resource so a future signed runtime artifact can be discovered in the packaged app. The current repository contains contract metadata only; packaged builds still refuse engine IPC until a verified executable bundle is present.

`download_runtime_artifact` is the acquisition boundary for a future distribution service. It requires a signed query URL, explicit approval, a required SHA-256, a bounded response, and an atomic destination write. It never executes the downloaded bytes; `verify_bundle` must pass before any runtime is considered usable.

The model registry can search the public Hugging Face model index and download one explicitly selected repository file. `frontierctl model-download-plan` resolves the exact revision URL, remote size, range support, conservative free-space requirement, and selected accelerator before bytes move. Official non-interactive Hub transfers use the Hugging Face cache and report whether `hf_xet` is available. Interactive desktop transfers select the cancellable backend they will actually use. The dependency-free fallback uses bounded parallel HTTP ranges for large files, preserves completed segments for resume, reassembles atomically, streams SHA-256 verification without loading the model into memory, and reports elapsed time plus throughput.

Desktop transfers run as separate workers backed by the durable job ledger. The UI polls recorded state, bytes, throughput, cancellation, failure, and integrity results instead of simulating progress. Retrying a cancelled or failed transfer creates a child job and reuses retained range segments. Successful transfer hashes are reused during registration, avoiding a second full read of a large model. Downloading never changes `capability_state` from `unvalidated`.
