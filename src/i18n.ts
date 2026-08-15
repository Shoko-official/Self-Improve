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
    projectLedgerTitle: "Project ledger unavailable",
    projectCountOne: "local project",
    projectCountMany: "local projects",
    projectLedgerDescription: "Projects, instructions, sessions, search, and reasoning profiles persist in the local Frontier store. The controls below are development-only until Frontier ships a managed engine runtime.",
    newProjectInstructions: "New project and instructions",
    researchWorkspace: "Research workspace",
    projectInstructions: "Project instructions",
    createProject: "Create project",
    searchLocalSessions: "Search all local sessions",
    sessionTitleLiteral: "Literal session title",
    searchSessions: "Search sessions",
    noMatchingSessions: "No local sessions match this literal query",
    noProjects: "No local projects yet",
    loadingProjectLedger: "Loading local project ledger…",
    archive: "Archive",
    sessionLedger: "SESSION LEDGER",
    loadingSessions: "Loading sessions",
    saveInstructions: "Save instructions",
    newSessionReasoning: "New session and reasoning effort",
    initialAnalysis: "Initial analysis",
    createSession: "Create session",
    unstar: "Unstar",
    star: "Star",
    fork: "Fork",
    noSessions: "No sessions in this project",
    refreshProjectLedger: "Refresh project ledger",
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
    projectLedgerTitle: "Registre des projets indisponible",
    projectCountOne: "projet local",
    projectCountMany: "projets locaux",
    projectLedgerDescription: "Les projets, instructions, sessions, recherches et profils de raisonnement sont conservés dans le registre local Frontier. Ces contrôles restent réservés au développement jusqu’à la livraison d’un moteur géré.",
    newProjectInstructions: "Nouveau projet et instructions",
    researchWorkspace: "Espace de recherche",
    projectInstructions: "Instructions du projet",
    createProject: "Créer le projet",
    searchLocalSessions: "Rechercher toutes les sessions locales",
    sessionTitleLiteral: "Titre exact de session",
    searchSessions: "Rechercher les sessions",
    noMatchingSessions: "Aucune session locale ne correspond à cette recherche exacte",
    noProjects: "Aucun projet local pour le moment",
    loadingProjectLedger: "Chargement du registre local des projets…",
    archive: "Archiver",
    sessionLedger: "REGISTRE DES SESSIONS",
    loadingSessions: "Chargement des sessions",
    saveInstructions: "Enregistrer les instructions",
    newSessionReasoning: "Nouvelle session et effort de raisonnement",
    initialAnalysis: "Analyse initiale",
    createSession: "Créer la session",
    unstar: "Retirer des favoris",
    star: "Ajouter aux favoris",
    fork: "Dupliquer",
    noSessions: "Aucune session dans ce projet",
    refreshProjectLedger: "Actualiser le registre des projets",
  },
} as const;

export type SurfaceMessageKey = keyof typeof surfaceMessages.en;

export function surfaceText(language: Language, key: SurfaceMessageKey): string {
  return surfaceMessages[language][key];
}
