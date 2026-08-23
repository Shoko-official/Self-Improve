# Verification / experiment - local model benchmark

## Question and utility

Measure whether the locally available GGUF models can execute the real task families through Shoko's runtime and identify the strongest verified candidate.

## Type

Empirical, computational, comparative.

## Competing hypotheses

- H1: a larger local model improves rubric success enough to justify its latency and memory cost.
- H2: a smaller local model provides better end-to-end utility because it completes more tasks within the same budget.
- H3: apparent gains come from prompt leakage or runtime differences rather than model behavior.

## Inputs and controls

Use fixed prompts, fixed task order, a public calibration set and a held-out set. Do not include expected answers in prompts. Keep model path and runtime version in every record.

## Metrics decided before observation

- task success: binary rubric result with evidence;
- citation support: supported citations divided by required citations;
- code correctness: tests passed divided by tests required;
- RAG recall@k: held-out source hit rate;
- latency: wall time to complete output in milliseconds;
- throughput: generated tokens per second when reported by runtime;
- memory: runtime-reported or measured peak when available.

## Risks

Prompt leakage, evaluator bias, unsupported online claims, stale sources, model-specific formatting, runtime startup cost, and incomplete outputs.

## Verdict

To be filled only from raw run records and held-out scoring.
