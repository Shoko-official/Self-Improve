import { invoke } from "@tauri-apps/api/core";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ModelsSurface } from "./ModelsSurface";
import { AutomationsSurface } from "./AutomationsSurface";
import {
  Bot,
  Boxes,
  Cable,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Code2,
  Command,
  Cpu,
  FileStack,
  FlaskConical,
  FolderKanban,
  Library,
  MessageSquare,
  Moon,
  PanelLeftOpen,
  PanelRightOpen,
  Plus,
  Play,
  Puzzle,
  RefreshCw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sun,
  TerminalSquare,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { surfaceText, type Language } from "./i18n";

type CapabilityReport = { operatingSystem: string; architecture: string; logicalCores: number; capturedAt: number; };
type EngineDoctorReport = { checked_at: string; host: { logical_cores: number; machine: string; release: string; system: string; }; limits: string[]; protocol_version: number; status: string; };
type ClaimRecord = { id: string; claim_type: string; status: "draft" | "supported" | "disputed" | "retracted"; text: string; uncertainty: string; evidence: Array<{ evidence_uri: string; selector: string }>; };
type ProjectRecord = { id: string; name: string; instructions: string; archived_at: string | null; created_at: string; };
type SessionRecord = { id: string; title: string; parent_session_id: string | null; reasoning_effort: string; starred: number; created_at: string; };
type JobRecord = { id: string; project_id: string; operation: string; state: string; created_at: string; };
type GenerationRecord = { id: string; project_id: string; runtime: string; model: string; state: string; output: string; diagnostic: { code: string } | null; };
type ArtifactRecord = { id: string; name: string; media_type: string; created_at: string; };
type EnvironmentRecord = { name: string; language: string; executable: string | null; python_version: string | null; package_fingerprint: string | null; packages: Record<string, string>; };
type AgentActivity = { project_id: string; plan: string | null; todos: Array<{ id: string; text: string; state: string }>; tool_calls: Array<{ id: string; tool_name: string; created_at: string; state: string; request: { model?: string }; result: { error?: string; output_chars?: number } }>; };
type KernelResult = { project_id: string; execution: { state: string; stdout: string; stderr: string; error?: string }; job: { id: string; state: string; diagnostic: { code: string } | null; events: Array<{ kind: string; created_at: string }> } };
type Surface = "chat" | "workspaces" | "models" | "science" | "artifacts" | "automations" | "mcp" | "skills" | "extensions" | "compute" | "kernel" | "settings";
type Theme = "light" | "dark";
type NavigationItem = { id: Surface; icon: LucideIcon; en: string; fr: string };

const navigation: NavigationItem[] = [
  { id: "chat", icon: MessageSquare, en: "Chat", fr: "Discussion" },
  { id: "workspaces", icon: FolderKanban, en: "Projects", fr: "Projets" },
  { id: "models", icon: Boxes, en: "Models", fr: "Modèles" },
  { id: "science", icon: FlaskConical, en: "Science", fr: "Science" },
  { id: "artifacts", icon: FileStack, en: "Artifacts", fr: "Artefacts" },
  { id: "automations", icon: Workflow, en: "Automations", fr: "Automatisations" },
  { id: "mcp", icon: Cable, en: "MCP", fr: "MCP" },
  { id: "skills", icon: Library, en: "Skills", fr: "Skills" },
  { id: "extensions", icon: Puzzle, en: "Extensions", fr: "Extensions" },
  { id: "compute", icon: Cpu, en: "Compute", fr: "Calcul" },
  { id: "kernel", icon: TerminalSquare, en: "Kernel", fr: "Kernel" },
  { id: "settings", icon: Settings, en: "Settings", fr: "Réglages" },
];

export function App() {
  const [surface, setSurface] = useState<Surface>("chat");
  const [language, setLanguage] = useState<Language>(() => localStorage.getItem("frontier-language") === "fr" ? "fr" : "en");
  const [theme, setTheme] = useState<Theme>(() => localStorage.getItem("frontier-theme") === "light" ? "light" : "dark");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [chatKey, setChatKey] = useState(0);
  const [report, setReport] = useState<CapabilityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [engineReport, setEngineReport] = useState<EngineDoctorReport | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [projectRecords, setProjectRecords] = useState<ProjectRecord[] | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const activeItem = navigation.find(item => item.id === surface) ?? navigation[0];
  const ActiveIcon = activeItem.icon;
  const activeProjects = projectRecords?.filter(project => project.archived_at === null) ?? [];

  async function probe() {
    setError(null);
    try {
      setReport(await invoke<CapabilityReport>("capability_report"));
    } catch {
      setError(language === "fr" ? "La sonde native est disponible uniquement dans l’application Shoko's LLM." : "The native probe is available only in the Shoko's LLM desktop app.");
    }
  }

  async function probeEngine() {
    setEngineError(null);
    try {
      setEngineReport(await invoke<EngineDoctorReport>("engine_doctor_development"));
    } catch (reason) {
      const desktopRuntime = "__TAURI_INTERNALS__" in window;
      setEngineError(desktopRuntime && reason instanceof Error ? reason.message : (language === "fr" ? "Le diagnostic du moteur est disponible uniquement dans l'application desktop." : "The engine diagnostic is available only in the desktop app."));
    }
  }

  async function refreshWorkspaces() {
    setWorkspaceError(null);
    try {
      setProjectRecords((await invoke<{ projects: ProjectRecord[] }>("workspace_projects_development")).projects);
    } catch (reason) {
      setWorkspaceError(reason instanceof Error ? reason.message : "FR-PROJECT-STORE-UNAVAILABLE");
    }
  }

  async function createWorkspace(name: string) {
    await invoke("create_workspace_project_development", { name });
    await refreshWorkspaces();
  }

  function startNewChat() {
    setChatKey(value => value + 1);
    setSurface("chat");
  }

  useEffect(() => {
    void probe();
    void probeEngine();
    void refreshWorkspaces();
  }, []);

  useEffect(() => {
    document.documentElement.lang = language;
    localStorage.setItem("frontier-language", language);
  }, [language]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    localStorage.setItem("frontier-theme", theme);
  }, [theme]);

  useEffect(() => {
    document.title = "Shoko's LLM | " + (language === "fr" ? activeItem.fr : activeItem.en);
  }, [activeItem, language]);

  useEffect(() => {
    function handleKeyboardShortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "n") {
        event.preventDefault();
        startNewChat();
      }
    }
    window.addEventListener("keydown", handleKeyboardShortcut);
    return () => window.removeEventListener("keydown", handleKeyboardShortcut);
  }, []);

  return (
    <div className={"app-frame" + (sidebarOpen ? "" : " sidebar-collapsed") + (inspectorOpen ? "" : " inspector-collapsed")}>
      <aside className="primary-sidebar" aria-label={language === "fr" ? "Navigation principale" : "Primary navigation"}>
        <div className="sidebar-brand">
          <button className="brand-button" type="button" onClick={startNewChat} aria-label={language === "fr" ? "Nouvelle discussion" : "New chat"}>
            <span className="brand-glyph"><Bot size={17} /></span>
            <span>Shoko's LLM</span>
          </button>
          <button className="icon-button sidebar-collapse" type="button" onClick={() => setSidebarOpen(false)} aria-label={language === "fr" ? "Réduire la navigation" : "Collapse navigation"}>
            <ChevronLeft size={17} />
          </button>
        </div>

        <button className="new-chat-button" type="button" onClick={startNewChat}>
          <Plus size={16} />
          <span>{language === "fr" ? "Nouvelle discussion" : "New chat"}</span>
          <kbd>Ctrl N</kbd>
        </button>

        <nav className="sidebar-nav" aria-label={language === "fr" ? "Sections" : "Sections"}>
          <p className="nav-label">{language === "fr" ? "Espace de travail" : "Workspace"}</p>
          {navigation.slice(0, 3).map(item => <NavigationButton key={item.id} item={item} language={language} current={surface} onSelect={setSurface} />)}
          <p className="nav-label">{language === "fr" ? "Outils" : "Tools"}</p>
          {navigation.slice(3, 9).map(item => <NavigationButton key={item.id} item={item} language={language} current={surface} onSelect={setSurface} />)}
          <p className="nav-label">{language === "fr" ? "Système" : "System"}</p>
          {navigation.slice(9).map(item => <NavigationButton key={item.id} item={item} language={language} current={surface} onSelect={setSurface} />)}
        </nav>

        <div className="project-shortlist">
          <div className="project-shortlist-title">
            <span>{language === "fr" ? "Projets locaux" : "Local projects"}</span>
            <button className="icon-button" type="button" onClick={() => setSurface("workspaces")} aria-label={language === "fr" ? "Gérer les projets" : "Manage projects"}>
              <Plus size={14} />
            </button>
          </div>
          {activeProjects.slice(0, 4).map(project => (
            <button key={project.id} className="project-shortcut" type="button" onClick={() => setSurface("workspaces")}>
              <FolderKanban size={14} />
              <span>{project.name}</span>
            </button>
          ))}
          {activeProjects.length === 0 && <p className="sidebar-empty">{workspaceError ? (language === "fr" ? "Registre indisponible" : "Store unavailable") : (language === "fr" ? "Aucun projet" : "No projects")}</p>}
        </div>

        <div className="sidebar-boundary">
          <ShieldCheck size={15} />
          <span>{language === "fr" ? "Données locales par défaut" : "Local data by default"}</span>
        </div>
      </aside>

      {!sidebarOpen && (
        <button className="icon-button sidebar-expand" type="button" onClick={() => setSidebarOpen(true)} aria-label={language === "fr" ? "Ouvrir la navigation" : "Open navigation"}>
          <PanelLeftOpen size={18} />
        </button>
      )}

      <main className="workspace-shell">
        <header className="workspace-header">
          <div className="workspace-heading">
            <ActiveIcon size={18} />
            <div>
              <p>Shoko's LLM</p>
              <h1>{language === "fr" ? activeItem.fr : activeItem.en}</h1>
            </div>
          </div>
          <div className="header-actions">
            <label className="language-control">
              <span>{language === "fr" ? "Langue" : "Language"}</span>
              <select value={language} onChange={event => setLanguage(event.target.value as Language)}>
                <option value="en">EN</option>
                <option value="fr">FR</option>
              </select>
            </label>
            <button className="icon-button" type="button" onClick={() => setTheme(value => value === "dark" ? "light" : "dark")} aria-label={theme === "dark" ? "Use light theme" : "Use dark theme"}>
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button className="icon-button" type="button" onClick={() => setInspectorOpen(value => !value)} aria-label={language === "fr" ? "Afficher le contexte" : "Show context"}>
              <PanelRightOpen size={17} />
            </button>
          </div>
        </header>

        <div className="workspace-grid">
          <section className="workspace-content" aria-label={language === "fr" ? activeItem.fr : activeItem.en}>
            {surface === "chat" && <ChatSurface key={chatKey} projects={projectRecords} language={language} onNavigate={setSurface} />}
            {surface === "workspaces" && <WorkspaceSurface projects={projectRecords} error={workspaceError} refresh={refreshWorkspaces} create={createWorkspace} />}
            {surface === "models" && <ModelsSurface report={report} error={error} probe={probe} engineReport={engineReport} engineError={engineError} probeEngine={probeEngine} projects={projectRecords} language={language} />}
            {surface === "science" && <ScienceWorkbench projects={projectRecords} language={language} />}
            {surface === "artifacts" && <><ArtifactsSurface /><AnnotationSurface /></>}
            {surface === "automations" && <AutomationsSurface projects={projectRecords} language={language} />}
            {surface === "mcp" && <RegistrySurface kind="connectors" language={language} projects={projectRecords} />}
            {surface === "skills" && <RegistrySurface kind="skills" language={language} projects={projectRecords} />}
            {surface === "extensions" && <RegistrySurface kind="extensions" language={language} projects={projectRecords} />}
            {surface === "compute" && <ComputeSurface />}
            {surface === "kernel" && <KernelSurface projects={projectRecords} />}
            {surface === "settings" && <SettingsSurface />}
          </section>

          {inspectorOpen && surface !== "science" && (
            <aside className="context-panel" aria-label={language === "fr" ? "Contexte" : "Context"}>
              <div className="context-header">
                <div>
                  <p className="context-kicker">{language === "fr" ? "Contexte" : "Context"}</p>
                  <h2>{language === "fr" ? "État local" : "Local state"}</h2>
                </div>
                <button className="icon-button" type="button" onClick={() => setInspectorOpen(false)} aria-label={language === "fr" ? "Fermer le contexte" : "Close context"}>
                  <ChevronRight size={17} />
                </button>
              </div>
              <dl className="context-list">
                <div><dt>{language === "fr" ? "Moteur" : "Engine"}</dt><dd>{engineReport?.status ?? (engineError ? (language === "fr" ? "Indisponible" : "Unavailable") : (language === "fr" ? "Vérification" : "Checking"))}</dd></div>
                <div><dt>{language === "fr" ? "Projets actifs" : "Active projects"}</dt><dd>{activeProjects.length}</dd></div>
                <div><dt>{language === "fr" ? "Hôte" : "Host"}</dt><dd>{report ? report.operatingSystem + " " + report.architecture : (language === "fr" ? "Non détecté" : "Not detected")}</dd></div>
                <div><dt>{language === "fr" ? "Cœurs logiques" : "Logical cores"}</dt><dd>{report?.logicalCores ?? "N/A"}</dd></div>
              </dl>
              <div className="context-actions">
                <button type="button" onClick={() => setSurface("models")}><Boxes size={15} />{language === "fr" ? "Gérer les modèles" : "Manage models"}</button>
                <button type="button" onClick={() => setSurface("compute")}><Cpu size={15} />{language === "fr" ? "Ouvrir le calcul" : "Open compute"}</button>
                <button type="button" onClick={() => setSurface("settings")}><Settings size={15} />{language === "fr" ? "Ouvrir les réglages" : "Open settings"}</button>
              </div>
              <div className="context-note">
                <ShieldCheck size={16} />
                <p>{language === "fr" ? "Aucun fournisseur distant n’est configuré. Les requêtes restent locales." : "No remote provider is configured. Requests remain local."}</p>
              </div>
            </aside>
          )}
        </div>
      </main>
    </div>
  );
}

function NavigationButton({ item, language, current, onSelect }: { item: NavigationItem; language: Language; current: Surface; onSelect: (surface: Surface) => void }) {
  const Icon = item.icon;
  return (
    <button type="button" className="nav-button" onClick={() => onSelect(item.id)} aria-current={current === item.id ? "page" : undefined}>
      <Icon size={16} />
      <span>{language === "fr" ? item.fr : item.en}</span>
    </button>
  );
}

type SlashCommand = {
  name: string;
  icon: LucideIcon;
  en: string;
  fr: string;
  target?: Surface;
  action?: "doctor" | "clear";
};

const slashCommands: SlashCommand[] = [
  { name: "/new", icon: Plus, en: "Clear the current draft and output", fr: "Effacer le brouillon et la sortie", action: "clear" },
  { name: "/projects", icon: FolderKanban, en: "Open local projects", fr: "Ouvrir les projets locaux", target: "workspaces" },
  { name: "/models", icon: Boxes, en: "Open model management", fr: "Ouvrir la gestion des modèles", target: "models" },
  { name: "/automations", icon: Workflow, en: "Open local AI pipelines", fr: "Ouvrir les pipelines IA locaux", target: "automations" },
  { name: "/mcp", icon: Cable, en: "Inspect MCP connectors", fr: "Inspecter les connecteurs MCP", target: "mcp" },
  { name: "/skills", icon: Library, en: "Inspect installed skills", fr: "Inspecter les skills installés", target: "skills" },
  { name: "/extensions", icon: Puzzle, en: "Inspect executable extensions", fr: "Inspecter les extensions exécutables", target: "extensions" },
  { name: "/science", icon: FlaskConical, en: "Open the science workbench", fr: "Ouvrir l’espace Science", target: "science" },
  { name: "/doctor", icon: ShieldCheck, en: "Run the local engine diagnostic", fr: "Exécuter le diagnostic du moteur local", action: "doctor" },
  { name: "/settings", icon: Settings, en: "Open application settings", fr: "Ouvrir les réglages", target: "settings" },
];

function ChatSurface({ projects, language, onNavigate }: { projects: ProjectRecord[] | null; language: Language; onNavigate: (surface: Surface) => void }) {
  const activeProjects = projects?.filter(project => project.archived_at === null) ?? [];
  const [projectId, setProjectId] = useState("");
  const [model, setModel] = useState("");
  const [prompt, setPrompt] = useState("");
  const [lastPrompt, setLastPrompt] = useState<string | null>(null);
  const [activity, setActivity] = useState<AgentActivity | null>(null);
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [availableSkills, setAvailableSkills] = useState<RegistryEntry[]>([]);
  const [skillId, setSkillId] = useState("");

  useEffect(() => {
    const nextProjectId = activeProjects.some(project => project.id === projectId) ? projectId : activeProjects[0]?.id ?? "";
    if (nextProjectId !== projectId) setProjectId(nextProjectId);
  }, [activeProjects, projectId]);

  useEffect(() => {
    if (!projectId) {
      setActivity(null);
      return;
    }
    void refreshActivity(projectId);
  }, [projectId]);

  useEffect(() => {
    void invoke<{ skills: RegistryEntry[] }>("scientific_skills_development")
      .then(result => setAvailableSkills(result.skills.filter(skill => skill.availability === "validated-manifest")))
      .catch(() => setAvailableSkills([]));
  }, []);

  const filteredCommands = useMemo(() => {
    const query = prompt.startsWith("/") ? prompt.toLowerCase() : "";
    return slashCommands.filter(command => command.name.startsWith(query));
  }, [prompt]);

  async function refreshActivity(nextProjectId = projectId) {
    if (!nextProjectId) return;
    try {
      setActivity(await invoke<AgentActivity>("local_agent_activity_development", { projectId: nextProjectId }));
    } catch {
      setActivity(null);
    }
  }

  async function runCommand(command: SlashCommand) {
    setCommandPaletteOpen(false);
    setPrompt("");
    if (command.target) {
      onNavigate(command.target);
      return;
    }
    if (command.action === "clear") {
      setLastPrompt(null);
      setOutput(null);
      setError(null);
      setActivity(null);
      return;
    }
    if (command.action === "doctor") {
      setBusy(true);
      setError(null);
      setLastPrompt(command.name);
      try {
        const result = await invoke<EngineDoctorReport>("engine_doctor_development");
        setOutput(JSON.stringify(result, null, 2));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "FR-ENGINE-UNAVAILABLE");
      } finally {
        setBusy(false);
      }
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const trimmedPrompt = prompt.trim();
    if (trimmedPrompt.startsWith("/")) {
      const command = slashCommands.find(item => item.name === trimmedPrompt.toLowerCase());
      if (command) {
        await runCommand(command);
        return;
      }
      setError(language === "fr" ? "Commande inconnue. Ouvrez la liste avec le bouton / ." : "Unknown command. Open the list with the / button.");
      return;
    }
    if (!projectId || !model.trim() || !trimmedPrompt) return;
    setBusy(true);
    setError(null);
    setOutput(null);
    setLastPrompt(trimmedPrompt);
    setPrompt("");
    try {
      const result = await invoke<{ output: string }>("run_local_agent_development", { projectId, model: model.trim(), prompt: trimmedPrompt, skillIds: skillId ? [skillId] : [] });
      setOutput(result.output);
      await refreshActivity(projectId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "FR-AGENT-RUN-FAILED");
      await refreshActivity(projectId);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="chat-workspace">
      <div className="chat-transcript" aria-live="polite">
        {!lastPrompt && !activity && (
          <div className="chat-empty">
            <span className="empty-icon"><Bot size={22} /></span>
            <h2>{language === "fr" ? "Que doit faire Shoko's LLM ?" : "What should Shoko's LLM do?"}</h2>
            <p>{language === "fr" ? "Choisissez un projet et un modèle local. Tapez / pour ouvrir les commandes." : "Choose a project and an exact local model. Type / to open commands."}</p>
            {!projectId && <button type="button" onClick={() => onNavigate("workspaces")}><FolderKanban size={15} />{language === "fr" ? "Créer un projet" : "Create a project"}</button>}
          </div>
        )}

        {lastPrompt && (
          <article className="chat-message user-message">
            <p className="message-author">{language === "fr" ? "Vous" : "You"}</p>
            <div>{lastPrompt}</div>
          </article>
        )}

        {busy && (
          <div className="execution-state">
            <RefreshCw size={15} className="spin" />
            <span>{language === "fr" ? "Exécution locale en cours" : "Running locally"}</span>
          </div>
        )}

        {error && (
          <div className="inline-error" role="alert">
            <CircleAlert size={17} />
            <div><strong>{language === "fr" ? "Exécution interrompue" : "Run stopped"}</strong><p>{error}</p></div>
          </div>
        )}

        {output !== null && (
          <article className="chat-message assistant-message">
            <div className="assistant-heading"><span className="assistant-mark"><Bot size={15} /></span><span>Shoko's LLM</span></div>
            <MarkdownContent content={output} />
          </article>
        )}

        {activity && (
          <section className="activity-ledger">
            <div className="activity-heading"><Code2 size={16} /><h3>{language === "fr" ? "Activité du projet" : "Project activity"}</h3></div>
            <div className="activity-grid">
              <div><span>{language === "fr" ? "Plan" : "Plan"}</span><p>{activity.plan ?? (language === "fr" ? "Aucun plan enregistré" : "No recorded plan")}</p></div>
              <div><span>Todos</span><p>{activity.todos.length ? activity.todos.map(todo => todo.state + ": " + todo.text).join("\n") : (language === "fr" ? "Aucun todo enregistré" : "No recorded todo")}</p></div>
              <div><span>{language === "fr" ? "Outils" : "Tools"}</span><p>{activity.tool_calls.length ? activity.tool_calls.map(call => call.state + ": " + call.tool_name).join("\n") : (language === "fr" ? "Aucun appel d’outil" : "No tool call")}</p></div>
            </div>
          </section>
        )}
      </div>

      <form className="chat-composer" onSubmit={event => void submit(event)}>
        {commandPaletteOpen && (
          <div className="command-palette" role="listbox" aria-label={language === "fr" ? "Commandes slash" : "Slash commands"}>
            <div className="command-title"><Command size={15} /><span>{language === "fr" ? "Commandes" : "Commands"}</span><kbd>Esc</kbd></div>
            {filteredCommands.map(command => {
              const CommandIcon = command.icon;
              return (
                <button key={command.name} type="button" onClick={() => void runCommand(command)}>
                  <CommandIcon size={15} />
                  <span><strong>{command.name}</strong><small>{language === "fr" ? command.fr : command.en}</small></span>
                </button>
              );
            })}
            {filteredCommands.length === 0 && <p>{language === "fr" ? "Aucune commande correspondante" : "No matching command"}</p>}
          </div>
        )}
        <div className="composer-context">
          <select value={projectId} onChange={event => setProjectId(event.target.value)} aria-label={language === "fr" ? "Projet" : "Project"} disabled={activeProjects.length === 0}>
            {activeProjects.length === 0 && <option value="">{language === "fr" ? "Aucun projet actif" : "No active project"}</option>}
            {activeProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
          <input value={model} onChange={event => setModel(event.target.value)} placeholder={language === "fr" ? "Modèle local exact, par exemple qwen3" : "Exact local model, for example qwen3"} aria-label={language === "fr" ? "Modèle local" : "Local model"} />
          <select value={skillId} onChange={event => setSkillId(event.target.value)} aria-label={language === "fr" ? "Skill optionnel" : "Optional skill"}>
            <option value="">{language === "fr" ? "Sans skill" : "No skill"}</option>
            {availableSkills.map(skill => <option value={skill.id} key={skill.id}>{skill.name ?? skill.id}</option>)}
          </select>
        </div>
        <textarea
          value={prompt}
          onChange={event => { setPrompt(event.target.value); setCommandPaletteOpen(event.target.value.startsWith("/")); }}
          onKeyDown={event => { if (event.key === "Escape") setCommandPaletteOpen(false); }}
          placeholder={language === "fr" ? "Demandez une modification, une analyse ou tapez /" : "Ask for a change, analysis, or type /"}
          rows={3}
        />
        <div className="composer-toolbar">
          <button className="composer-tool" type="button" onClick={() => { setPrompt(value => value.startsWith("/") ? value : "/"); setCommandPaletteOpen(true); }} aria-label={language === "fr" ? "Ouvrir les commandes" : "Open commands"}>
            <Command size={16} /><span>{language === "fr" ? "Commandes" : "Commands"}</span>
          </button>
          <span className="composer-boundary"><ShieldCheck size={14} />{language === "fr" ? "Local" : "Local"}</span>
          <button className="send-button" type="submit" disabled={busy || (!prompt.trim().startsWith("/") && (!projectId || !model.trim() || !prompt.trim()))} aria-label={language === "fr" ? "Exécuter" : "Run"}>
            <Send size={16} />
          </button>
        </div>
      </form>
    </section>
  );
}

export function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children, ...props }) => <a {...props} target="_blank" rel="noreferrer">{children}</a>,
          img: ({ alt, ...props }) => <img {...props} alt={alt ?? ""} loading="lazy" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

type RegistryTool = { name: string; title?: string; description?: string; inputSchema?: Record<string, unknown>; annotations?: Record<string, unknown> };
type RegistryEntry = { id: string; name?: string; description?: string; capabilities: string[]; network: string; availability: string; source?: string; version?: string; license?: string; tools?: RegistryTool[] };
type McpProbe = { connectors: RegistryEntry[]; failures: Array<{ id: string; code: string }>; detected: number };

function RegistrySurface({ kind, language, projects }: { kind: "connectors" | "skills" | "extensions"; language: Language; projects: ProjectRecord[] | null }) {
  const [entries, setEntries] = useState<RegistryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [probeApproval, setProbeApproval] = useState(false);
  const [probe, setProbe] = useState<McpProbe | null>(null);
  const [selectedConnectorId, setSelectedConnectorId] = useState("");
  const [selectedToolName, setSelectedToolName] = useState("");
  const [projectId, setProjectId] = useState("");
  const [toolArguments, setToolArguments] = useState("{}");
  const [callApproval, setCallApproval] = useState(false);
  const [callOutput, setCallOutput] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const activeProjects = projects?.filter(project => project.archived_at === null) ?? [];

  async function load() {
    setError(null);
    setEntries(null);
    try {
      const command = kind === "connectors" ? "scientific_connectors_development" : kind === "skills" ? "scientific_skills_development" : "extensions_development";
      const result = await invoke<Record<string, RegistryEntry[]>>(command);
      setEntries(result[kind]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "FR-REGISTRY-UNAVAILABLE");
    }
  }

  useEffect(() => { void load(); }, [kind]);
  useEffect(() => { if (!projectId && activeProjects[0]) setProjectId(activeProjects[0].id); }, [activeProjects, projectId]);

  const isConnectors = kind === "connectors";
  const isExtensions = kind === "extensions";
  const RegistryIcon = isConnectors ? Cable : isExtensions ? Puzzle : Library;
  const mergedEntries = isConnectors && entries
    ? [...new Map([...entries, ...(probe?.connectors ?? [])].map(entry => [entry.id, entry])).values()]
    : entries;
  const visibleEntries = mergedEntries?.filter(entry => `${entry.name ?? ""} ${entry.id} ${entry.description ?? ""} ${entry.capabilities.join(" ")}`.toLowerCase().includes(query.trim().toLowerCase())) ?? null;
  const selectedConnector = probe?.connectors.find(connector => connector.id === selectedConnectorId) ?? null;

  async function verifyMcp() {
    setBusy(true);
    setError(null);
    try {
      const result = await invoke<McpProbe>("probe_integrations_development", { approved: probeApproval });
      setProbe(result);
      const first = result.connectors[0];
      setSelectedConnectorId(first?.id ?? "");
      setSelectedToolName(first?.tools?.[0]?.name ?? "");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "FR-MCP-PROBE");
    } finally {
      setProbeApproval(false);
      setBusy(false);
    }
  }

  async function invokeTool(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setCallOutput(null);
    try {
      const argumentsValue = JSON.parse(toolArguments) as unknown;
      if (!argumentsValue || typeof argumentsValue !== "object" || Array.isArray(argumentsValue)) throw new Error("FR-MCP-ARGUMENTS");
      const result = await invoke<{ result: Record<string, unknown> }>("call_mcp_tool_development", { projectId, serverId: selectedConnectorId, toolName: selectedToolName, arguments: argumentsValue, approved: callApproval });
      setCallOutput(result.result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "FR-MCP-CALL");
    } finally {
      setCallApproval(false);
      setBusy(false);
    }
  }
  return (
    <section className="registry-page">
      <div className="page-intro">
        <span className="page-icon"><RegistryIcon size={18} /></span>
        <div>
          <h2>{isConnectors ? "MCP" : isExtensions ? (language === "fr" ? "Extensions" : "Extensions") : "Skills"}</h2>
          <p>{isConnectors
            ? (language === "fr" ? "Connecteurs disponibles et limites réseau déclarées par le moteur local." : "Available connectors and network boundaries reported by the local engine.")
            : isExtensions
              ? (language === "fr" ? "Seules les extensions validées et exécutables apparaissent ici." : "Only validated and executable extensions appear here.")
              : (language === "fr" ? "Skills installés, capacités et limites d’exécution déclarées par le moteur local." : "Installed skills, capabilities, and execution boundaries reported by the local engine.")}</p>
        </div>
      </div>

      <div className="registry-controls">
        <label><Search size={14} /><input aria-label={language === "fr" ? "Filtrer le registre" : "Filter registry"} value={query} onChange={event => setQuery(event.target.value)} placeholder={language === "fr" ? "Filtrer le registre" : "Filter registry"} /></label>
        {isConnectors && <><label className="approval-check"><input type="checkbox" checked={probeApproval} onChange={event => setProbeApproval(event.target.checked)} />{language === "fr" ? "J'autorise ce probe à démarrer les processus configurés et accéder au réseau" : "I approve this probe starting configured processes and accessing the network"}</label><button className="minor-action" type="button" onClick={() => void verifyMcp()} disabled={busy || !probeApproval}><RefreshCw size={14} />{language === "fr" ? "Vérifier les MCP installés" : "Verify installed MCP"}</button>{probe && <p className="registry-probe-note">{probe.detected} {language === "fr" ? "détectés" : "detected"}, {probe.connectors.length} {language === "fr" ? "vérifiés" : "verified"}, {probe.failures.length} {language === "fr" ? "indisponibles masqués" : "unavailable hidden"}</p>}</>}
      </div>

      {error && <div className="inline-error" role="alert"><CircleAlert size={17} /><div><strong>{language === "fr" ? "Action impossible" : "Action unavailable"}</strong><p>{error}</p><button type="button" onClick={() => void load()}><RefreshCw size={14} />{language === "fr" ? "Recharger le registre" : "Reload registry"}</button></div></div>}

      {entries === null && !error && <div className="registry-loading" aria-label={language === "fr" ? "Chargement" : "Loading"}><span /><span /><span /></div>}

      {visibleEntries && (
        <div className="registry-list">
          {visibleEntries.map(entry => (
            <article key={entry.id} className="registry-row">
              <div className="registry-symbol"><RegistryIcon size={17} /></div>
              <div className="registry-main"><h3>{entry.name ?? entry.id}</h3><p>{entry.description ?? entry.capabilities.join(", ")}</p><small>{entry.id}</small></div>
              <dl><div><dt>{language === "fr" ? "Réseau" : "Network"}</dt><dd>{entry.network}</dd></div><div><dt>{language === "fr" ? "Disponibilité" : "Availability"}</dt><dd>{entry.availability}</dd></div></dl>
              {entry.tools && entry.tools.length > 0 && <button className="minor-action registry-select" type="button" onClick={() => { setSelectedConnectorId(entry.id); setSelectedToolName(entry.tools?.[0]?.name ?? ""); setCallApproval(false); setCallOutput(null); }}>{language === "fr" ? "Ouvrir les outils" : "Open tools"}</button>}
            </article>
          ))}
          {visibleEntries.length === 0 && <div className="registry-empty"><p>{language === "fr" ? "Aucune intégration exécutable détectée. Les extensions non connectables restent masquées." : "No executable integration detected. Extensions that cannot connect remain hidden."}</p></div>}
        </div>
      )}

      {isConnectors && selectedConnector && <form className="mcp-tool-panel" onSubmit={event => void invokeTool(event)}><div className="automation-heading"><Cable size={17} /><div><span>MCP TOOLS</span><h3>{selectedConnector.id}</h3></div></div><label>{language === "fr" ? "Projet" : "Project"}<select value={projectId} onChange={event => setProjectId(event.target.value)} required>{activeProjects.length === 0 && <option value="">{language === "fr" ? "Aucun projet actif" : "No active project"}</option>}{activeProjects.map(project => <option value={project.id} key={project.id}>{project.name}</option>)}</select></label><label>{language === "fr" ? "Outil vérifié" : "Verified tool"}<select value={selectedToolName} onChange={event => { setSelectedToolName(event.target.value); setCallApproval(false); }} required>{selectedConnector.tools?.map(tool => <option value={tool.name} key={tool.name}>{tool.title ?? tool.name}</option>)}</select></label><label>{language === "fr" ? "Arguments JSON" : "JSON arguments"}<textarea value={toolArguments} onChange={event => setToolArguments(event.target.value)} spellCheck={false} /></label><label className="approval-check"><input type="checkbox" checked={callApproval} onChange={event => setCallApproval(event.target.checked)} />{language === "fr" ? "J'approuve explicitement cet appel MCP" : "I explicitly approve this MCP call"}</label><button className="action" type="submit" disabled={busy || !projectId || !selectedToolName || !callApproval}><Play size={14} />{language === "fr" ? "Appeler l'outil" : "Call tool"}</button>{callOutput && <div className="mcp-tool-output">{mcpMarkdown(callOutput) && <MarkdownContent content={mcpMarkdown(callOutput) ?? ""} />}<details><summary>{language === "fr" ? "Résultat structuré" : "Structured result"}</summary><pre className="agent-output">{JSON.stringify(callOutput, null, 2)}</pre></details></div>}</form>}
    </section>
  );
}

export function mcpMarkdown(output: Record<string, unknown>): string | null {
  if (!Array.isArray(output.content)) return null;
  const text = output.content.find(item => item && typeof item === "object" && "type" in item && item.type === "text" && "text" in item && typeof item.text === "string");
  return text && typeof text === "object" && "text" in text ? String(text.text) : null;
}

function ScienceWorkbench({ projects, language }: { projects: ProjectRecord[] | null; language: Language }) {
  const [panel, setPanel] = useState<"notebook" | "artifacts">("notebook");
  return (
    <section className="science-workbench">
      <div className="science-conversation">
        <div className="science-titlebar">
          <div><p>{language === "fr" ? "Projet scientifique" : "Science project"}</p><h2>{language === "fr" ? "Recherche et preuves" : "Research and evidence"}</h2></div>
          <div className="science-panel-switch" role="group" aria-label={language === "fr" ? "Panneau scientifique" : "Science panel"}>
            <button type="button" aria-pressed={panel === "notebook"} onClick={() => setPanel("notebook")}><Code2 size={15} />Notebook</button>
            <button type="button" aria-pressed={panel === "artifacts"} onClick={() => setPanel("artifacts")}><FileStack size={15} />{language === "fr" ? "Artefacts" : "Artifacts"}</button>
          </div>
        </div>
        <ScienceSurface />
        <ReviewerSurface />
      </div>
      <aside className="science-inspector" aria-label={panel === "notebook" ? "Notebook" : (language === "fr" ? "Artefacts" : "Artifacts")}>
        <div className="science-inspector-header">
          <div className="science-file-icon">{panel === "notebook" ? <Code2 size={16} /> : <FileStack size={16} />}</div>
          <div><p>{panel === "notebook" ? "python.ipynb" : (language === "fr" ? "Artefacts du projet" : "Project artifacts")}</p><span>{language === "fr" ? "Stockage local" : "Local storage"}</span></div>
        </div>
        <div className="science-inspector-body">
          {panel === "notebook" ? <KernelSurface projects={projects} /> : <><ArtifactsSurface /><AnnotationSurface /></>}
        </div>
      </aside>
    </section>
  );
}

function ReviewerSurface() { const language = localStorage.getItem("frontier-language") === "fr" ? "fr" : "en"; const [findings, setFindings] = useState<Array<{ claim_id: string; code: string; severity: string; message: string }> | null>(null); const [error, setError] = useState<string | null>(null); async function review() { try { setError(null); setFindings((await invoke<{ findings: Array<{ claim_id: string; code: string; severity: string; message: string }> }>("review_scientific_claims_development")).findings); } catch (reason) { setError(reason instanceof Error ? reason.message : surfaceText(language, "reviewer")); } } useEffect(() => { void review(); }, []); return <section className="surface review-panel"><div className="surface-mark">EVIDENCE REVIEW</div><h2>{findings ? `${findings.length} ${surfaceText(language, findings.length === 1 ? "openFindingOne" : "openFindingMany")}` : surfaceText(language, "reviewer")}</h2><p>Findings identify missing evidence. They do not rerun analyses or grant scientific approval.</p>{error && <p className="agent-error">{error}</p>}{findings && <Evidence rows={findings.length ? findings.map(finding => `${finding.severity}: ${finding.code} · claim ${finding.claim_id} · ${finding.message}`) : [surfaceText(language, "noEvidenceGaps")]} />}<button className="action" onClick={() => void review()}>Run evidence review</button></section>; }

function AnnotationSurface() { const language = localStorage.getItem("frontier-language") === "fr" ? "fr" : "en"; const [versionId, setVersionId] = useState(""); const [targetKind, setTargetKind] = useState("text"); const [selector, setSelector] = useState('{"offset":0}'); const [body, setBody] = useState(""); const [annotations, setAnnotations] = useState<Array<{ id: string; target_kind: string; body: string; consumed_at: string | null }> | null>(null); const [error, setError] = useState<string | null>(null); async function load() { try { setError(null); setAnnotations((await invoke<{ annotations: Array<{ id: string; target_kind: string; body: string; consumed_at: string | null }> }>("project_annotations_development", { artifactVersionId: versionId })).annotations); } catch (reason) { setError(reason instanceof Error ? reason.message : surfaceText(language, "annotation")); } } async function create(event: FormEvent) { event.preventDefault(); try { await invoke("create_project_annotation_development", { artifactVersionId: versionId, targetKind, selector, body }); setBody(""); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : surfaceText(language, "annotation")); } } return <section className="surface annotation-panel"><div className="surface-mark">VERSIONED ANNOTATIONS</div><h2>Exact artifact feedback</h2><p>Annotations stay attached to the artifact version you name. A missing version is rejected.</p><form className="project-form" onSubmit={event => void create(event)}><label htmlFor="annotation-version">Artifact version, target, selector, and note</label><input id="annotation-version" value={versionId} onChange={event => setVersionId(event.target.value)} placeholder={surfaceText(language, "artifactVersionId")} required /><select value={targetKind} onChange={event => setTargetKind(event.target.value)}><option value="text">Text</option><option value="code">Code</option><option value="markdown">Markdown</option><option value="latex">LaTeX</option><option value="pdf_region">PDF region</option><option value="image_point">Image point</option><option value="html_element">HTML element</option><option value="transcript_region">Transcript region</option></select><input value={selector} onChange={event => setSelector(event.target.value)} placeholder='{"page":2}' required /><textarea value={body} onChange={event => setBody(event.target.value)} placeholder={surfaceText(language, "annotation")} required /><button className="action" type="submit">Save annotation</button></form>{error && <p className="agent-error">{error}</p>}<button className="minor-action" onClick={() => void load()}>Refresh annotations</button>{annotations && <Evidence rows={annotations.length ? annotations.map(annotation => `${annotation.target_kind}: ${annotation.body}`) : [surfaceText(language, "noOpenAnnotations")]} />}</section>; }

function KernelSurface({ projects }: { projects: ProjectRecord[] | null }) { const activeProjects = projects?.filter(project => project.archived_at === null) ?? []; const [projectId, setProjectId] = useState(""); const [code, setCode] = useState("print('Frontier kernel ready')"); const [result, setResult] = useState<KernelResult | null>(null); const [error, setError] = useState<string | null>(null); useEffect(() => { const next = activeProjects.some(project => project.id === projectId) ? projectId : activeProjects[0]?.id ?? ""; if (next !== projectId) setProjectId(next); }, [projects, projectId]); async function execute(event: FormEvent) { event.preventDefault(); if (!projectId) return; setError(null); try { setResult(await invoke<KernelResult>("kernel_execute_development", { projectId, code })); } catch (reason) { setError(reason instanceof Error ? reason.message : "Kernel execution failed."); } } async function restart() { if (!projectId) return; setError(null); try { await invoke("kernel_restart_development", { projectId }); setResult(null); } catch (reason) { setError(reason instanceof Error ? reason.message : "Kernel restart failed."); } } return <section className="surface"><div className="surface-mark">PYTHON KERNEL</div><h2>{activeProjects.length ? "Persistent project workspace" : "Create an active project first"}</h2><p>Each active project owns one local Python namespace while the control service runs. Execution is recorded as a durable job. R is not enabled unless its live probe succeeds.</p>{activeProjects.length > 0 && <><form className="project-form kernel-form" onSubmit={event => void execute(event)}><label htmlFor="kernel-project">Project and Python cell</label><select id="kernel-project" value={projectId} onChange={event => setProjectId(event.target.value)}>{activeProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select><textarea className="kernel-editor" value={code} onChange={event => setCode(event.target.value)} spellCheck={false} required /><button className="action" type="submit">Run Python cell</button><button className="minor-action" type="button" onClick={() => void restart()}>Restart kernel</button></form>{error && <p className="agent-error">{error}</p>}{result && <><Evidence rows={[`Job ${result.job.id}: ${result.job.state}`, ...result.job.events.map(event => `${event.created_at}: ${event.kind}`), result.job.diagnostic?.code ?? "No terminal diagnostic"]} />{result.execution.stdout && <pre className="agent-output">{result.execution.stdout}</pre>}{result.execution.stderr && <pre className="agent-output">{result.execution.stderr}</pre>}{result.execution.error && <pre className="agent-output">{result.execution.error}</pre>}</>}</>}</section>; }

function AgentSurface({ projects }: { projects: ProjectRecord[] | null }) { const activeProjects = projects?.filter(project => project.archived_at === null) ?? []; const [projectId, setProjectId] = useState(""); const [model, setModel] = useState(""); const [prompt, setPrompt] = useState(""); const [activity, setActivity] = useState<AgentActivity | null>(null); const [output, setOutput] = useState<string | null>(null); const [error, setError] = useState<string | null>(null); useEffect(() => { const nextProjectId = activeProjects.some(project => project.id === projectId) ? projectId : activeProjects[0]?.id ?? ""; if (nextProjectId !== projectId) setProjectId(nextProjectId); }, [projects, projectId]); async function refresh() { if (!projectId) { setActivity(null); return; } setError(null); try { setActivity(await invoke<AgentActivity>("local_agent_activity_development", { projectId })); } catch (reason) { setError(reason instanceof Error ? reason.message : "Agent activity is unavailable."); } } async function run(event: FormEvent) { event.preventDefault(); if (!projectId) return; setError(null); setOutput(null); try { const result = await invoke<{ output: string }>("run_local_agent_development", { projectId, model, prompt }); setOutput(result.output); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Local agent run failed."); await refresh(); } } useEffect(() => { void refresh(); }, [projectId]); return <section className="surface"><div className="surface-mark">LOCAL AGENT</div><h2>{activeProjects.length ? "Plan, output, and tool ledger" : "Create an active project first"}</h2><p>The agent calls only the exact local Ollama model you enter. It does not fall back to another model or provider. Failed runtime checks remain in the project activity ledger.</p>{activeProjects.length > 0 && <><form className="project-form agent-form" onSubmit={event => void run(event)}><label htmlFor="agent-project">Project, installed model, and task</label><select id="agent-project" value={projectId} onChange={event => setProjectId(event.target.value)}>{activeProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select><input value={model} onChange={event => setModel(event.target.value)} placeholder="Installed Ollama model" required /><textarea value={prompt} onChange={event => setPrompt(event.target.value)} placeholder="Local task" required /><button className="action" type="submit">Run local agent</button></form>{error && <p className="agent-error">{error}</p>}{output !== null && <pre className="agent-output">{output}</pre>}{activity && <><div className="agent-ledger"><div><span className="surface-mark">PLAN</span><p>{activity.plan ?? "No durable plan recorded yet."}</p></div><div><span className="surface-mark">TODOS</span><Evidence rows={activity.todos.length ? activity.todos.map(todo => `${todo.state}: ${todo.text}`) : ["No local todo recorded"]} /></div><div><span className="surface-mark">TOOL ACTIVITY</span><Evidence rows={activity.tool_calls.length ? activity.tool_calls.map(call => `${call.created_at || "legacy record"}: ${call.state}: ${call.tool_name} (${call.request.model ?? "no model"})${call.result.error ? `; ${call.result.error}` : ""}`) : ["No local tool call recorded"]} /></div></div><button className="minor-action" onClick={() => void refresh()}>Refresh agent activity</button></>}</>}</section>; }

function WorkspaceSurface({ projects, error, refresh, create: _create }: { projects: ProjectRecord[] | null; error: string | null; refresh: () => Promise<void>; create: (name: string) => Promise<void> }) { const language = localStorage.getItem("frontier-language") === "fr" ? "fr" : "en"; const [name, setName] = useState(""); const [instructions, setInstructions] = useState(""); const [selected, setSelected] = useState<string | null>(null); const [sessions, setSessions] = useState<SessionRecord[] | null>(null); const [sessionTitle, setSessionTitle] = useState(""); const [reasoningEffort, setReasoningEffort] = useState("standard"); const [searchQuery, setSearchQuery] = useState(""); const [searchResults, setSearchResults] = useState<SessionRecord[] | null>(null); const [message, setMessage] = useState<string | null>(null); const activeProject = projects?.find(project => project.id === selected); async function loadSessions(projectId: string) { setSelected(projectId); setSessions(null); setMessage(null); try { setSessions((await invoke<{ sessions: SessionRecord[] }>("workspace_sessions_development", { projectId })).sessions); } catch (reason) { setMessage(reason instanceof Error ? reason.message : "Session ledger unavailable."); } } async function submitProject(event: FormEvent) { event.preventDefault(); setMessage(null); try { await invoke("create_workspace_project_development", { name, instructions }); setName(""); setInstructions(""); await refresh(); } catch (reason) { setMessage(reason instanceof Error ? reason.message : "Project creation failed."); } } async function updateInstructions() { if (!selected) return; try { await invoke("set_workspace_project_instructions_development", { projectId: selected, instructions }); await refresh(); } catch (reason) { setMessage(reason instanceof Error ? reason.message : "Project instruction update failed."); } } async function submitSession(event: FormEvent) { event.preventDefault(); if (!selected) return; setMessage(null); try { await invoke("create_workspace_session_development", { projectId: selected, title: sessionTitle, parentSessionId: null, reasoningEffort }); setSessionTitle(""); await loadSessions(selected); } catch (reason) { setMessage(reason instanceof Error ? reason.message : "Session creation failed."); } } async function search(event: FormEvent) { event.preventDefault(); try { setSearchResults((await invoke<{ sessions: SessionRecord[] }>("search_workspace_sessions_development", { query: searchQuery, projectId: null })).sessions); } catch (reason) { setMessage(reason instanceof Error ? reason.message : "Session search failed."); } } async function archive(projectId: string) { await invoke("archive_workspace_project_development", { projectId }); await refresh(); if (selected === projectId) { setSelected(null); setSessions(null); } } async function toggleStar(session: SessionRecord) { await invoke("set_workspace_session_starred_development", { sessionId: session.id, starred: !session.starred }); if (selected) await loadSessions(selected); } async function setEffort(session: SessionRecord, value: string) { await invoke("set_workspace_session_reasoning_development", { sessionId: session.id, reasoningEffort: value }); if (selected) await loadSessions(selected); } async function fork(session: SessionRecord) { if (!selected) return; await invoke("create_workspace_session_development", { projectId: selected, title: `${session.title} fork`, parentSessionId: session.id, reasoningEffort: session.reasoning_effort }); await loadSessions(selected); } return <section className="surface"><div className="surface-mark">PROJECT LEDGER</div><h2>{projects ? `${projects.length} ${surfaceText(language, projects.length === 1 ? "projectCountOne" : "projectCountMany")}` : surfaceText(language, "projectLedgerTitle")}</h2><p>Projects, instructions, sessions, search, and reasoning profiles persist in the local Frontier store. The controls below are development-only until Frontier ships a managed engine runtime.</p><form className="project-form" onSubmit={event => void submitProject(event)}><label htmlFor="project-name">New project and instructions</label><input id="project-name" value={name} onChange={event => setName(event.target.value)} placeholder={surfaceText(language, "researchWorkspace")} required /><input value={instructions} onChange={event => setInstructions(event.target.value)} placeholder={surfaceText(language, "projectInstructions")} /><button className="action" type="submit">Create project</button></form><form className="project-form" onSubmit={event => void search(event)}><label htmlFor="session-search">Search all local sessions</label><input id="session-search" value={searchQuery} onChange={event => setSearchQuery(event.target.value)} placeholder={surfaceText(language, "sessionTitleLiteral")} required /><button className="action" type="submit">Search sessions</button></form>{searchResults && <Evidence rows={searchResults.length ? searchResults.map(session => `${session.title} | ${session.reasoning_effort}`) : [surfaceText(language, "noMatchingSessions")]} />}{message && <p>{message}</p>}{projects ? <div className="workspace-list">{projects.length ? projects.map(project => <div key={project.id} className="workspace-row"><button className="workspace-name" onClick={() => { setInstructions(project.instructions); void loadSessions(project.id); }}>{project.name}{project.archived_at ? " (archived)" : ""}</button>{!project.archived_at && <button className="minor-action" onClick={() => void archive(project.id)}>Archive</button>}</div>) : <p>No local projects yet</p>}</div> : <p>{error ?? surfaceText(language, "loadingProjectLedger")}</p>}{selected && <div className="session-ledger"><div className="surface-mark">SESSION LEDGER</div><h2>{sessions ? `${sessions.length} session${sessions.length === 1 ? "" : "s"}` : surfaceText(language, "loadingSessions")}</h2>{activeProject && !activeProject.archived_at && <div className="project-form"><label htmlFor="project-instructions">Project instructions</label><input id="project-instructions" value={instructions} onChange={event => setInstructions(event.target.value)} /><button className="action" onClick={() => void updateInstructions()}>Save instructions</button></div>}<form className="project-form" onSubmit={event => void submitSession(event)}><label htmlFor="session-title">New session and reasoning effort</label><input id="session-title" value={sessionTitle} onChange={event => setSessionTitle(event.target.value)} placeholder={surfaceText(language, "initialAnalysis")} required /><select value={reasoningEffort} onChange={event => setReasoningEffort(event.target.value)}><option value="compact">Compact</option><option value="standard">Standard</option><option value="extended">Extended</option></select><button className="action" type="submit">Create session</button></form>{sessions && <div className="workspace-list">{sessions.length ? sessions.map(session => <div key={session.id} className="workspace-row"><span>{session.title}{session.parent_session_id ? " (fork)" : ""}</span><span><select value={session.reasoning_effort} onChange={event => void setEffort(session, event.target.value)} aria-label={`Reasoning effort for ${session.title}`}><option value="compact">Compact</option><option value="standard">Standard</option><option value="extended">Extended</option></select><button className="minor-action" onClick={() => void toggleStar(session)}>{session.starred ? surfaceText(language, "unstar") : surfaceText(language, "star")}</button><button className="minor-action" onClick={() => void fork(session)}>Fork</button></span></div>) : <p>No sessions in this project</p>}</div>}</div>}<button className="action" onClick={() => void refresh()}>Refresh project ledger</button></section>; }
function ScienceSurface() { const [queries, setQueries] = useState<Array<{ id: string; query_text: string; source: string; result_count: number; accessed_at: string }> | null>(null); const [claims, setClaims] = useState<ClaimRecord[] | null>(null); const [query, setQuery] = useState(""); const [source, setSource] = useState("local fixture"); const [count, setCount] = useState("0"); const [claimType, setClaimType] = useState("observation"); const [claimText, setClaimText] = useState(""); const [uncertainty, setUncertainty] = useState(""); const [evidenceUri, setEvidenceUri] = useState(""); const [evidenceSelector, setEvidenceSelector] = useState(""); const [error, setError] = useState<string | null>(null); async function refresh() { try { setQueries((await invoke<{ queries: Array<{ id: string; query_text: string; source: string; result_count: number; accessed_at: string }> }>("literature_queries_development")).queries); } catch (reason) { setError(reason instanceof Error ? reason.message : "Literature ledger unavailable."); } } async function refreshClaims() { try { setClaims((await invoke<{ claims: ClaimRecord[] }>("scientific_claims_development")).claims); } catch (reason) { setError(reason instanceof Error ? reason.message : "Scientific claims ledger unavailable."); } } async function submit(event: FormEvent) { event.preventDefault(); try { await invoke("record_literature_query_development", { query, source, resultCount: Number(count) }); setQuery(""); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Literature record failed."); } } async function submitClaim(event: FormEvent) { event.preventDefault(); try { await invoke("create_scientific_claim_development", { claimType, claimText, uncertainty, evidenceUri, evidenceSelector }); setClaimText(""); setUncertainty(""); setEvidenceUri(""); setEvidenceSelector(""); await refreshClaims(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Scientific claim creation failed."); } } async function setClaimStatus(claimId: string, claimStatus: ClaimRecord["status"]) { try { await invoke("set_scientific_claim_status_development", { claimId, claimStatus }); await refreshClaims(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Scientific claim update failed."); } } useEffect(() => { void refresh(); void refreshClaims(); }, []); return <section className="surface"><div className="surface-mark">RESEARCH RECORD</div><h2>{queries ? `${queries.length} reproducible literature quer${queries.length === 1 ? "y" : "ies"}` : "Literature ledger"}</h2><p>Record the exact query, source, filters, access time, and observed result count. No remote literature connector is configured on this machine.</p><form className="project-form" onSubmit={event => void submit(event)}><label htmlFor="literature-query">Query, source, and result count</label><input id="literature-query" value={query} onChange={event => setQuery(event.target.value)} placeholder="Single-cell quality control" required /><input value={source} onChange={event => setSource(event.target.value)} required /><input type="number" min="0" value={count} onChange={event => setCount(event.target.value)} required /><button className="action" type="submit">Record query</button></form>{error && <p>{error}</p>}<button className="action" onClick={() => void refresh()}>Refresh literature ledger</button>{queries && <Evidence rows={queries.map(item => `${item.query_text} | ${item.source} | ${item.result_count} results`)} />}<div className="claim-ledger"><div className="surface-mark">CLAIM EVIDENCE SPINE</div><h2>{claims ? `${claims.length} scientific claim${claims.length === 1 ? "" : "s"}` : "Scientific claim ledger"}</h2><p>Claims are local records, not conclusions. Their type, uncertainty, status, and exact evidence locator remain inspectable.</p><form className="project-form claim-form" onSubmit={event => void submitClaim(event)}><label htmlFor="claim-text">Type, claim, uncertainty, and evidence locator</label><select value={claimType} onChange={event => setClaimType(event.target.value)}><option value="source">Source</option><option value="observation">Observation</option><option value="computed">Computed</option><option value="inference">Inference</option><option value="hypothesis">Hypothesis</option></select><input id="claim-text" value={claimText} onChange={event => setClaimText(event.target.value)} placeholder="Claim text" required /><input value={uncertainty} onChange={event => setUncertainty(event.target.value)} placeholder="Uncertainty or limitation" required /><input value={evidenceUri} onChange={event => setEvidenceUri(event.target.value)} placeholder="artifact://..." required /><input value={evidenceSelector} onChange={event => setEvidenceSelector(event.target.value)} placeholder="table:row-2" required /><button className="action" type="submit">Record claim</button></form><button className="action" onClick={() => void refreshClaims()}>Refresh claim ledger</button>{claims && <div className="claim-list">{claims.length ? claims.map(claim => <article className="claim-row" key={claim.id}><div className="claim-meta"><span>{claim.claim_type}</span><span>{claim.status}</span></div><strong>{claim.text}</strong><p>Uncertainty: {claim.uncertainty}</p>{claim.evidence.map(item => <code key={`${item.evidence_uri}:${item.selector}`}>{item.evidence_uri} · {item.selector}</code>)}<div><button className="minor-action" onClick={() => void setClaimStatus(claim.id, "supported")}>Mark supported</button><button className="minor-action" onClick={() => void setClaimStatus(claim.id, "disputed")}>Mark disputed</button><button className="minor-action" onClick={() => void setClaimStatus(claim.id, "retracted")}>Retract</button></div></article>) : <p>No local claims yet</p>}</div>}</div></section>; }
function ArtifactsSurface() { const [projectId, setProjectId] = useState(""); const [artifacts, setArtifacts] = useState<ArtifactRecord[] | null>(null); const [name, setName] = useState(""); const [content, setContent] = useState(""); const [searchQuery, setSearchQuery] = useState(""); const [searchResults, setSearchResults] = useState<Array<ArtifactRecord & { latest_version: number | null; latest_content_hash: string | null }> | null>(null); const [versions, setVersions] = useState<Array<{ version: number; content_hash: string; execution_log: Record<string, string> }> | null>(null); const [error, setError] = useState<string | null>(null); async function load() { try { setArtifacts((await invoke<{ artifacts: ArtifactRecord[] }>("project_artifacts_development", { projectId })).artifacts); } catch (reason) { setError(reason instanceof Error ? reason.message : "Artifact ledger unavailable."); } } async function submit(event: FormEvent) { event.preventDefault(); try { await invoke("create_project_artifact_development", { projectId, name, mediaType: "text/markdown", content }); setName(""); setContent(""); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Artifact creation failed."); } } async function search(event: FormEvent) { event.preventDefault(); try { setError(null); setSearchResults((await invoke<{ artifacts: Array<ArtifactRecord & { latest_version: number | null; latest_content_hash: string | null }> }>("search_project_artifacts_development", { query: searchQuery, projectId: projectId || null, mediaType: null })).artifacts); } catch (reason) { setError(reason instanceof Error ? reason.message : "Artifact search failed."); } } async function inspect(artifactId: string) { setVersions((await invoke<{ versions: Array<{ version: number; content_hash: string; execution_log: Record<string, string> }> }>("project_artifact_versions_development", { artifactId })).versions); } return <section className="surface"><div className="surface-mark">LINEAGE</div><h2>{artifacts ? `${artifacts.length} versioned artifact${artifacts.length === 1 ? "" : "s"}` : "Artifact ledger"}</h2><p>Payloads are content-addressed and versions retain independent messages and execution-log provenance.</p><form className="project-form" onSubmit={event => void submit(event)}><label htmlFor="artifact-project">Project ID, artifact name, and markdown content</label><input id="artifact-project" value={projectId} onChange={event => setProjectId(event.target.value)} placeholder="Project ID" required /><input value={name} onChange={event => setName(event.target.value)} placeholder="Result name" required /><input value={content} onChange={event => setContent(event.target.value)} placeholder="Markdown content" /><button className="action" type="submit">Save artifact</button></form><form className="project-form" onSubmit={event => void search(event)}><label htmlFor="artifact-search">Literal artifact discovery</label><input id="artifact-search" value={searchQuery} onChange={event => setSearchQuery(event.target.value)} placeholder="Name fragment" required /><button className="minor-action" type="submit">Search artifacts</button></form>{error && <p>{error}</p>}<button className="action" onClick={() => void load()}>Refresh artifacts</button>{searchResults && <Evidence rows={searchResults.length ? searchResults.map(artifact => `${artifact.name} · ${artifact.media_type} · latest v${artifact.latest_version ?? "not saved"}`) : ["No matching artifact names."]} />}{artifacts && <div className="workspace-list">{artifacts.map(artifact => <div className="workspace-row" key={artifact.id}><span>{artifact.name}</span><button className="minor-action" onClick={() => void inspect(artifact.id)}>Inspect versions</button></div>)}</div>}{versions && <Evidence rows={versions.map(version => `v${version.version}: ${version.content_hash.slice(0, 12)}; execution ${version.execution_log.state ?? "recorded"}`)} />}</section>; }
function ComputeSurface() { const [jobs, setJobs] = useState<JobRecord[] | null>(null); const [generations, setGenerations] = useState<GenerationRecord[] | null>(null); const [projectId, setProjectId] = useState(""); const [operation, setOperation] = useState("local.inspect"); const [error, setError] = useState<string | null>(null); async function refresh() { setError(null); try { const [jobResult, generationResult] = await Promise.all([invoke<{ jobs: JobRecord[] }>("compute_jobs_development"), invoke<{ generations: GenerationRecord[] }>("local_generations_development")]); setJobs(jobResult.jobs); setGenerations(generationResult.generations); } catch (reason) { setError(reason instanceof Error ? reason.message : "Compute monitor unavailable."); } } async function submit(event: FormEvent) { event.preventDefault(); try { await invoke("enqueue_compute_job_development", { projectId, operation }); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Job enqueue failed."); } } async function cancel(jobId: string) { await invoke("cancel_compute_job_development", { jobId }); await refresh(); } async function retry(jobId: string) { await invoke("retry_compute_job_development", { jobId }); await refresh(); } useEffect(() => { void refresh(); }, []); return <section className="surface"><div className="surface-mark">SCHEDULER</div><h2>{jobs ? `${jobs.length} durable job${jobs.length === 1 ? "" : "s"}` : "Compute monitor unavailable"}</h2><p>Local jobs retain queued, running, cancellation-requested, cancelled, succeeded, and failed states. No remote host or cloud provider is configured.</p><form className="project-form" onSubmit={event => void submit(event)}><label htmlFor="job-project">Project ID and operation</label><input id="job-project" value={projectId} onChange={event => setProjectId(event.target.value)} placeholder="Project ID" required /><input value={operation} onChange={event => setOperation(event.target.value)} required /><button className="action" type="submit">Queue job</button></form>{error && <p>{error}</p>}{jobs && <div className="workspace-list">{jobs.length ? jobs.map(job => <div className="workspace-row" key={job.id}><span>{job.operation}: {job.state}</span>{["queued", "running"].includes(job.state) && <button className="minor-action" onClick={() => void cancel(job.id)}>Cancel</button>}{["failed", "cancelled"].includes(job.state) && <button className="minor-action" onClick={() => void retry(job.id)}>Retry</button>}</div>) : <p>No jobs queued</p>}</div>}{generations && <Evidence rows={generations.length ? generations.map(generation => `${generation.runtime}/${generation.model}: ${generation.state}; ${generation.output || generation.diagnostic?.code || "no output"}`) : ["No persisted local generations. Install a compatible runtime before creating one."]} />}<button className="action" onClick={() => void refresh()}>Refresh compute monitor</button></section>; }
function SettingsSurface() { const [probe, setProbe] = useState<Record<string, unknown> | null>(null); const [language, setLanguage] = useState("python"); const [name, setName] = useState(""); const [environments, setEnvironments] = useState<EnvironmentRecord[]>([]); const [error, setError] = useState<string | null>(null); async function inspect(nextLanguage = language) { try { const result = await invoke<{ probe: Record<string, unknown>; manifests: EnvironmentRecord[] }>("scientific_environment_probe_development", { language: nextLanguage }); setProbe(result.probe); setEnvironments(result.manifests); } catch (reason) { setError(reason instanceof Error ? reason.message : "Environment probe unavailable."); } } async function create(event: FormEvent) { event.preventDefault(); setError(null); try { await invoke("create_python_environment_development", { name }); setName(""); await inspect("python"); } catch (reason) { setError(reason instanceof Error ? reason.message : "Python environment creation failed."); } } useEffect(() => { void inspect(); }, []); return <section className="surface"><div className="surface-mark">TRUST BOUNDARY</div><h2>Local environments</h2><p>Create an isolated Python environment with no package download. Its exact interpreter and empty package fingerprint remain local and inspectable.</p><form className="project-form" onSubmit={event => void create(event)}><label htmlFor="environment-name">New local Python environment</label><input id="environment-name" value={name} onChange={event => setName(event.target.value)} placeholder="analysis" pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,63}" required /><button className="action" type="submit">Create Python environment</button></form><div className="workspace-list"><div className="workspace-row"><button className="minor-action" onClick={() => { setLanguage("python"); void inspect("python"); }}>Probe Python</button><button className="minor-action" onClick={() => { setLanguage("r"); void inspect("r"); }}>Probe R</button></div></div>{error && <p>{error}</p>}{probe && <dl>{Object.entries(probe).map(([key, value]) => <><dt key={`${key}-term`}>{key}</dt><dd key={`${key}-value`}>{String(value)}</dd></>)}</dl>}{environments.length > 0 && <Evidence rows={environments.map(environment => `${environment.name}: ${environment.python_version ?? environment.language}; ${environment.executable ?? "no executable"}; ${environment.package_fingerprint ?? "no fingerprint"}`)} />}<Evidence rows={["Package download: none during creation", "Provider fallback: forbidden", "Remote egress: no provider configured"]} /></section>; }
function Surface({ mark, title, text, rows }: { mark: string; title: string; text: string; rows: string[] }) { return <section className="surface"><div className="surface-mark">{mark}</div><h2>{title}</h2><p>{text}</p><Evidence rows={rows} /></section>; }
function Evidence({ rows }: { rows: string[] }) { return <ul className="evidence">{rows.map(row => <li key={row}><span>verified state</span>{row}</li>)}</ul>; }
