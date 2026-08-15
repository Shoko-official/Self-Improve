export type Language = "en" | "fr";

const messages = {
  en: { workbench: "WORKBENCH", localBoundary: "Local data boundary active", noRemote: "No remote provider connected", language: "Language", workspaces: "Workspaces", workspacesCaption: "Projects and sessions", models: "Models", modelsCaption: "Runtime evidence", agent: "Agent", agentCaption: "Plans and activity", science: "Science", scienceCaption: "Research records", artifacts: "Artifacts", artifactsCaption: "Versioned outputs", compute: "Compute", computeCaption: "Durable jobs", settings: "Settings", settingsCaption: "Data boundaries" },
  fr: { workbench: "ATELIER", localBoundary: "Frontière de données locale active", noRemote: "Aucun fournisseur distant connecté", language: "Langue", workspaces: "Espaces de travail", workspacesCaption: "Projets et sessions", models: "Modèles", modelsCaption: "Preuves d’exécution", agent: "Agent", agentCaption: "Plans et activité", science: "Science", scienceCaption: "Dossiers de recherche", artifacts: "Artefacts", artifactsCaption: "Sorties versionnées", compute: "Calcul", computeCaption: "Tâches durables", settings: "Réglages", settingsCaption: "Frontières de données" },
} as const;

export type MessageKey = keyof typeof messages.en;

export function translate(language: Language, key: MessageKey): string {
  return messages[language][key];
}
