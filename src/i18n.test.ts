import { describe, expect, it } from "vitest";
import { translate } from "./i18n";

describe("translate", () => {
  it("resolves the primary navigation in both supported languages", () => {
    expect(translate("en", "workspaces")).toBe("Workspaces");
    expect(translate("fr", "workspaces")).toBe("Espaces de travail");
  });
});
