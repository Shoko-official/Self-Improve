import { describe, expect, it } from "vitest";
import { primaryNavigation, secondaryNavigation } from "./App";

describe("workspace navigation", () => {
  it("keeps the core workflows primary and exposes operational surfaces through tools", () => {
    expect(primaryNavigation.map(item => item.id)).toEqual(["chat", "workspaces", "models", "science"]);
    expect(secondaryNavigation.map(item => item.id)).toEqual(["artifacts", "automations", "plugins", "mcp", "skills", "extensions", "compute", "kernel"]);
  });
});
