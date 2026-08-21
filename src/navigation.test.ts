import { describe, expect, it } from "vitest";
import { primaryNavigation, resolveProjectId, secondaryNavigation } from "./App";

describe("workspace navigation", () => {
  it("keeps the core workflows primary and exposes operational surfaces through tools", () => {
    expect(primaryNavigation.map(item => item.id)).toEqual(["chat", "workspaces", "models", "science"]);
    expect(secondaryNavigation.map(item => item.id)).toEqual(["artifacts", "automations", "plugins", "mcp", "skills", "extensions", "compute", "kernel"]);
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
