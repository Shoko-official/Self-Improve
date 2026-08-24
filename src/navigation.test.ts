import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ChatSurface, compareBenchmarkRuns, localAgentModelOptions, primaryNavigation, resolveProjectId, secondaryNavigation } from "./App";

describe("workspace navigation", () => {
  it("keeps the core workflows primary and exposes operational surfaces through tools", () => {
    expect(primaryNavigation.map(item => item.id)).toEqual(["chat", "workspaces", "models", "science"]);
    expect(secondaryNavigation.map(item => item.id)).toEqual(["images", "audio", "artifacts", "automations", "plugins", "mcp", "skills", "extensions", "compute", "benchmarks", "kernel"]);
  });
});

describe("project-scoped chat navigation", () => {
  const projects = [
    { id: "alpha", name: "Alpha", instructions: "", archived_at: null, created_at: "2026-08-21" },
    { id: "beta", name: "Beta", instructions: "", archived_at: null, created_at: "2026-08-21" },
  ];

  it("prefers a project selected from the sidebar", () => {
    expect(resolveProjectId(projects, "beta", "alpha")).toBe("beta");
  });

  it("falls back when the selected project is no longer active", () => {
    expect(resolveProjectId(projects, "removed", "removed")).toBe("alpha");
  });
});

describe("first chat setup", () => {
  it("guides an empty workspace to the working projects surface", () => {
    const html = renderToStaticMarkup(createElement(ChatSurface, { projects: [], language: "en", onNavigate: () => undefined, preferredProjectId: "", onProjectChange: () => undefined }));

    expect(html).toContain("Create your first project");
    expect(html).toContain("Open projects");
  });
});

describe("benchmark comparison", () => {
  const base = { run_id: "a", status: "complete", model: "a.gguf", variant: "A", completed_at: 0, report_path: "a.json", macro_fraction: 0.5, latency_ms: 100 };

  it("reports score and latency deltas for complete runs", () => {
    expect(compareBenchmarkRuns(base, { ...base, run_id: "b", variant: "B", macro_fraction: 0.75, latency_ms: 130 })).toEqual({ valid: true, scoreDelta: 0.25, latencyDeltaMs: 30 });
  });

  it("rejects incomplete runs", () => {
    expect(compareBenchmarkRuns(base, { ...base, status: "failed" }).valid).toBe(false);
  });
});

describe("local agent model routing", () => {
  it("keeps LM Studio GGUF models on the independent Shoko runtime", () => {
    const options = localAgentModelOptions({
      shoko_gguf: { available: true, version: "b10517", path: "C:/runtime/llama-server.exe", reason: null, independent_of_lm_studio: true },
      ollama: { available: true, models: ["qwen3:4b"] },
      lm_studio_library: { available: true, models_root: "C:/Users/test/.lmstudio/models", models: [{ key: "qwen", display_name: "Qwen3 4B", path: "C:/models/qwen.gguf", size_bytes: 1, format: "gguf", execution_runtime: "shoko-managed-gguf" }] },
      registered_models: [],
    });
    expect(options.map(option => option.value)).toEqual(["gguf:C:/models/qwen.gguf", "qwen3:4b"]);
    expect(options[0].label).toContain("Shoko runtime");
    expect(options[0].source).toBe("shoko-gguf");
  });
});
