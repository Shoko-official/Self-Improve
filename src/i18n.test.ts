import { describe, expect, it } from "vitest";
import { surfaceText, translate } from "./i18n";

describe("translate", () => {
  it("resolves the primary navigation in both supported languages", () => {
    expect(translate("en", "workspaces")).toBe("Workspaces");
    expect(translate("fr", "workspaces")).toBe("Espaces de travail");
  });

  it("resolves primary surface copy in both supported languages", () => {
    expect(surfaceText("en", "evidenceReview")).toBe("Evidence review");
    expect(surfaceText("fr", "evidenceReview")).toBe("Revue des preuves");
    expect(surfaceText("fr", "run")).toBe("Exécuter");
  });

  it("resolves workspace form copy in both supported languages", () => {
    expect(surfaceText("en", "createProject")).toBe("Create project");
    expect(surfaceText("fr", "createProject")).toBe("Créer le projet");
    expect(surfaceText("fr", "refreshProjectLedger")).toBe("Actualiser le registre des projets");
    expect(surfaceText("en", "runEvidenceReview")).toBe("Run evidence review");
    expect(surfaceText("fr", "saveAnnotation")).toBe("Enregistrer l’annotation");
  });
});
