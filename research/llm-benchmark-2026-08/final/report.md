# Local benchmark report

## Scope

This report covers local runs through the independent Shoko GGUF runtime on Windows 11. The panel contains six families: research synthesis, code generation, bug fixing, agentic RAG, constrained reasoning, and online-research discipline. It is a local proxy, not a leaderboard or general capability claim.

## Historical comparison

| Model | Panel | Strict macro score | Notes |
| --- | --- | ---: | --- |
| Qwen3 4B | script, 384 tokens | 0.772 | Best observed proxy on the historical panel |
| Qwen3.5 9B | script, 384 tokens | 0.703 | Code execution passed; RAG and online checks were mixed |
| Gemma 4 26B-A4B | script, 256 tokens | 0.664 | Strong code and reasoning; bug-fix execution failed |
| Qwen3.6 35B-A3B | script, 256 tokens | 0.506 | Research passed; reasoning and RAG contract adherence were weak |

## Desktop Benchmark Lab run

The new application path was exercised with Qwen3 4B Q4_K_M, runtime `b10517`, 128 output tokens, and variant `qwen3-4b-cli-real`. All six tasks completed through `frontierctl benchmark-run`, with total measured latency 68,727.86 ms and strict macro score 0.569. The durable report is stored at `C:\Users\shoko\.frontier-data\benchmarks\20260824-012839-2b6200d3.json` on the measured host.

The run was complete at the runtime level, but the rubric exposed quality gaps: truncated code and bug-fix outputs, missing exact RAG source intervals, and incomplete arithmetic wording. Those are recorded as failures in the report rather than hidden by a success badge.

## Reproduction

```powershell
$env:PYTHONPATH = "engine"
python -m frontier_engine.cli --json benchmark-run `
  --model "C:\path\to\model.gguf" `
  --max-tokens 384 `
  --variant local-comparison
python -m frontier_engine.cli --json benchmark-reports
```

The desktop route is Tools, Benchmarks, then Run benchmark. The selected model must be a detected local GGUF file and the Shoko runtime must pass its probe. Runtime or model failures remain visible and do not count toward the score.

## Limitations

The panel is small, deterministic, and local. It does not measure GPU throughput, peak memory, multilingual quality, multimodal quality, or external web retrieval. The live online-research task tests abstention and search planning only. Results must be compared with matched prompts, token budgets, runtime versions, and host fingerprints.
