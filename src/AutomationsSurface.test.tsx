import { describe, expect, it } from "vitest";
import { toPipelineSteps } from "./AutomationsSurface";

describe("pipeline editor payload", () => {
  it("normalizes dependencies, retries, and typed configuration", () => {
    const steps = toPipelineSteps([
      { key: "review", kind: "skill", target: "evidence-review", prompt: "", code: "", query: "", dependencies: "", retries: "1" },
      { key: "summary", kind: "model", target: "qwen3", prompt: "Summarize", code: "", query: "", dependencies: " review, ", retries: "2" },
    ]);
    expect(steps[0]).toMatchObject({ key: "review", config: { skill_id: "evidence-review" }, max_retries: 1 });
    expect(steps[1]).toMatchObject({ key: "summary", config: { model: "qwen3", prompt: "Summarize" }, depends_on: ["review"], max_retries: 2 });
  });

  it("only emits connector fields used by the selected executor", () => {
    const [step] = toPipelineSteps([{ key: "search", kind: "connector", target: "huggingface-model-catalog", prompt: "", code: "", query: "biology", dependencies: "", retries: "0" }]);
    expect(step.config).toEqual({ connector_id: "huggingface-model-catalog", query: "biology", limit: 10 });
  });
});
