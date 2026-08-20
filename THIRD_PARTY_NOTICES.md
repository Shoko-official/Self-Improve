# Third-party notices

## Scientific reference audit

`Shoko-official/Claude-Science-System-Prompts`, commit `a55a1709d36534d42462b51f61f9859bf4ab23b6`, was inspected as an Apache-2.0 implementation reference. Frontier has not reused its source text, scripts, schemas, or assets in this revision.

## Application dependencies

`SBOM.cdx.json` is the generated CycloneDX 1.6 inventory for the pinned pnpm, Cargo, and managed-engine build dependencies. It includes direct and transitive package identities, versions, available license expressions, registry hashes where the lock exposes them, and SHA-256 identities for the three source locks.

The primary desktop stack includes Tauri under Apache-2.0 or MIT, React and the Markdown toolchain under MIT-compatible licenses, and Lucide under ISC. The SBOM is authoritative for exact package versions.

## Managed engine distribution

The managed engine is frozen with PyInstaller 6.20.0. PyInstaller is GPL-2.0-or-later with its bootloader exception for distributing generated applications. The package carries the exact PyInstaller notice at `runtime-packs/managed-engine/licenses/PYINSTALLER-COPYING.txt`.

The sidecar embeds CPython and its standard library. The package carries the applicable Python Software Foundation license at `runtime-packs/managed-engine/licenses/PYTHON-LICENSE.txt`.

Models, optional runtime packs, user-installed skills, MCP servers, and plugins are not included in the base installer. Their own licenses and provenance must be reviewed when installed.
