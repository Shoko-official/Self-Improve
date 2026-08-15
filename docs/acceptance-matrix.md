# Acceptance matrix

| Area | Status | Evidence |
| --- | --- | --- |
| Desktop launch | partially_verified | Tauri configuration, icon, and native capability command compile under the Visual Studio developer environment |
| Engine protocol | verified | `python -m frontier_engine doctor` fixture |
| Hardware probe | partially_verified | Static OS, architecture, and core probe implemented |
| Local text runtime | not_verifiable_here | No runtime pack installed |
| Remote providers | not_verifiable_here | No credential or provider configured |
| Science parity | not_verifiable_here | Baseline matrix created |
| Windows package | not_verifiable_here | Tauri release build is blocked by the host application-control policy while executing a Rust build script: `os error 4551` |
