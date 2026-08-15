export type Language = "en" | "fr";

const messages = {
  en: { workbench: "WORKBENCH", localBoundary: "Local data boundary active", noRemote: "No remote provider connected", language: "Language", workspaces: "Workspaces", workspacesCaption: "Projects and sessions", models: "Models", modelsCaption: "Runtime evidence", agent: "Agent", agentCaption: "Plans and activity", kernel: "Kernel", kernelCaption: "Persistent Python", science: "Science", scienceCaption: "Research records", artifacts: "Artifacts", artifactsCaption: "Versioned outputs", compute: "Compute", computeCaption: "Durable jobs", settings: "Settings", settingsCaption: "Data boundaries" },
  fr: { workbench: "ATELIER", localBoundary: "Frontière de données locale active", noRemote: "Aucun fournisseur distant connecté", language: "Langue", workspaces: "Espaces de travail", workspacesCaption: "Projets et sessions", models: "Modèles", modelsCaption: "Preuves d’exécution", agent: "Agent", agentCaption: "Plans et activité", kernel: "Kernel", kernelCaption: "Python persistant", science: "Science", scienceCaption: "Dossiers de recherche", artifacts: "Artefacts", artifactsCaption: "Sorties versionnées", compute: "Calcul", computeCaption: "Tâches durables", settings: "Réglages", settingsCaption: "Frontières de données" },
} as const;

export type MessageKey = keyof typeof messages.en;

export function translate(language: Language, key: MessageKey): string {
  return messages[language][key];
}

const surfaceMessages = {
  en: {
    evidenceReview: "Evidence review",
    exactArtifactFeedback: "Exact artifact feedback",
    persistentProjectWorkspace: "Persistent project workspace",
    localAgent: "Local agent",
    projectLedger: "Project ledger",
    trustBoundary: "Trust boundary",
    developmentEngine: "Development engine",
    noActiveProject: "Create an active project first",
    refresh: "Refresh",
    save: "Save",
    run: "Run",
  },
  fr: {
    evidenceReview: "Revue des preuves",
    exactArtifactFeedback: "Retour exact sur l’artefact",
    persistentProjectWorkspace: "Espace de travail persistant",
    localAgent: "Agent local",
    projectLedger: "Registre des projets",
    trustBoundary: "Frontière de confiance",
    developmentEngine: "Moteur de développement",
    noActiveProject: "Créez d’abord un projet actif",
    refresh: "Actualiser",
    save: "Enregistrer",
    run: "Exécuter",
  },
} as const;

export type SurfaceMessageKey = keyof typeof surfaceMessages.en;

export function surfaceText(language: Language, key: SurfaceMessageKey): string {
  return surfaceMessages[language][key];
}
