# Real local Shoko's LLM benchmark

## Question

Which locally available model and runtime configuration gives the strongest verified behavior across research synthesis, code generation and repair, agentic RAG, complex reasoning, and source-backed online research while remaining usable in Shoko's LLM?

## Scope

Included: models already present in the user's LM Studio library, Shoko's independent GGUF runtime, local RAG retrieval, deterministic task prompts, measured latency and throughput, and source-backed research workflows.

Excluded: claims about general intelligence, leaderboard rank, hosted model quality, hidden chain-of-thought, and benchmarks that cannot run through the application's declared runtime.

## Evaluation contract

- Record model path, runtime version, host fingerprint, prompt id, seed when supported, raw output, latency, and token metrics.
- Keep task families separate: research, code, bug fix, agentic RAG, reasoning, and online research.
- Use held-out prompts for any model selection decision.
- Report task success with a rubric and evidence, not only speed.
- Preserve failures and runtime-invalid attempts.

## Stopping criteria

Stop after every selected model has a complete run or a documented runtime failure, the held-out set is scored, and an independent review checks leakage, missing evidence, and overclaiming.
