# Benchmark methodology

The desktop Benchmark Lab runs six fixed families through the same independent Shoko GGUF runtime used for local chat: research synthesis, code generation, bug fixing, agentic RAG, constrained reasoning, and online-research discipline. A run is valid only when the selected local model file exists and the runtime starts successfully.

Each run records the model path, runtime version, variant label, token budget, host fingerprint, start and completion timestamps, per-task latency, raw output, failures, and a predeclared rubric. Generated Python is executed in a temporary process for the code and bug-fix tasks. RAG checks require exact source intervals and causal abstention. A failed task is retained and never converted into a pass.

The CLI entry points are `frontierctl benchmark-run --model PATH` and `frontierctl benchmark-reports`. The same commands are exposed in the desktop Benchmark Lab and persist JSON under the local data root in `benchmarks/`. Scores are arithmetic means over completed rubric tasks only. They are local proxy measurements and do not establish general model quality, leaderboard rank, or external performance.
