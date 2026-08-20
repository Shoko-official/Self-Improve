# Release evidence

## Windows x64 host package

Observed on 2026-08-20:

- Artifact: `src-tauri/target/debug/bundle/msi/Shoko's LLM_0.1.0_x64_en-US.msi`
- Profile: Rust debug profile with the `managed-engine` feature
- Signature: unsigned
- Size: 15,597,568 bytes
- SHA-256: `4b92da6784eb9bdd36e0851c3f147689c00c3142a4e4fedbc2188f404174b7c4`
- Managed sidecar size: 11,335,615 bytes
- Managed sidecar SHA-256: `3ee228c56e50759716437a313be63631b8a8d98ad7243ef201cd6aa0d7218917`
- SBOM: CycloneDX 1.6 with 740 unique locked components

The MSI was decompiled with the same WiX 3.14 toolchain used by Tauri. The extracted application, sidecar, managed-engine manifest, and SBOM were reconstructed in a temporary QA directory that was removed after verification. Running the extracted `frontier.exe --managed-engine-smoke` verified the sidecar hash through the Rust boundary and returned engine protocol version 1 with healthy status.

The optimized local Rust profile is not claimed as built. Windows application control blocked execution of the `web_atoms` release build script with `os error 4551`. The native package workflow builds optimized packages on Windows, Linux, macOS Apple silicon, and macOS Intel runners and repeats both sidecar and Rust-boundary smoke tests.

Unsigned artifacts are development evidence, not a trusted distribution channel. Signing and notarization require separately configured release credentials.

## Validation

- Python engine: 178 tests passed
- React interface: 16 tests passed
- Rust managed boundary: 3 tests passed
- Frontend production build: passed
- Direct sidecar doctor: healthy, protocol version 1
- Packaged Rust boundary smoke: healthy, protocol version 1
- Anti-slop source scan: 0 bans, 0 warnings
- Release gate with the documented dirty-worktree exception: passed

`cargo fmt --check` is not a release gate in this repository. It reports pre-existing formatting differences across `src-tauri/build.rs` and the existing one-line command handlers in `src-tauri/src/main.rs`. Applying it would create unrelated repository-wide formatting churn.
