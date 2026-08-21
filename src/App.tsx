import { invoke } from "@tauri-apps/api/core";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ModelsSurface } from "./ModelsSurface";
import { AutomationsSurface } from "./AutomationsSurface";
import {
  Bot,
  Bell,
  Boxes,
  Cable,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Code2,
  Command,
  Cpu,
  FileStack,
  FlaskConical,
  FolderKanban,
  Gauge,
  GitBranch,
  Library,
  ListTodo,
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
  Star,
  Sun,
  TerminalSquare,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { surfaceText, type Language } from "./i18n";

type CapabilityReport = { operatingSystem: string; architecture: string; logicalCores: number; capturedAt: number; };
type EngineDoctorReport = { checked_at: string; host: { logical_cores: number; machine: string; release: string; system: string; }; limits: string[]; protocol_version: number; status: string; };
type DesktopNotification = { id: string; source: string; severity: "info" | "warning" | "error"; title: string; body: string; deep_link: string; acknowledged_at: string | null; };
type ClaimRecord = { id: string; claim_type: string; status: "draft" | "supported" | "disputed" | "retracted"; text: string; uncertainty: string; evidence: Array<{ evidence_uri: string; selector: string }>; };
type ProjectRecord = { id: string; name: string; instructions: string; archived_at: string | null; created_at: string; };
type SessionRecord = { id: string; title: string; parent_session_id: string | null; reasoning_effort: string; starred: number; created_at: string; };
type JobRecord = { id: string; project_id: string; operation: string; state: string; created_at: string; };
type GenerationRecord = { id: string; project_id: string; runtime: string; model: string; state: string; output: string; diagnostic: { code: string } | null; };
type ArtifactRecord = { id: string; name: string; media_type: string; created_at: string; };
type EnvironmentRecord = { name: string; language: string; executable: string | null; python_version: string | null; runtime_version?: string | null; package_fingerprint: string | null; packages: Record<string, string>; };
type AgentActivity = { project_id: string; plan: string | null; plan_state: string | null; todos: Array<{ id: string; text: string; state: string }>; tool_calls: Array<{ id: string; tool_name: string; created_at: string; state: string; request: { model?: string }; result: { error?: string; output_chars?: number } }>; };
type LocalModelCatalog = { shoko_gguf: { available: boolean; version: string; path: string | null; reason: string | null; independent_of_lm_studio: boolean }; ollama: { available: boolean; models: string[]; reason?: string }; lm_studio_library: { available: boolean; models_root: string; models: Array<{ key: string; display_name: string; path: string; size_bytes: number; format: string; execution_runtime: string }> } };
type KernelResult = { project_id: string; execution: { state: string; stdout: string; stderr: string; error?: string }; job: { id: string; state: string; diagnostic: { code: string } | null; events: Array<{ kind: string; created_at: string }> } };
type FolderGrant = { id: string; path: string; operation: string; revoked_at: string | null };
type GitContext = { linked: boolean; repository?: boolean; path?: string; branch?: string; changes?: number; status?: string[]; remote?: string | null; reason?: string; ci?: { available: boolean; latest?: { status: string; conclusion: string; name: string; url: string; updatedAt: string } | null; reason?: string } };
type Surface = "chat" | "workspaces" | "models" | "science" | "artifacts" | "automations" | "plugins" | "mcp" | "skills" | "extensions" | "compute" | "kernel" | "settings";
type Theme = "light" | "dark";
type NavigationItem = { id: Surface; icon: LucideIcon; en: string; fr: string };

const navigation: NavigationItem[] = [
  { id: "chat", icon: MessageSquare, en: "Chat", fr: "Discussion" },
  { id: "workspaces", icon: FolderKanban, en: "Projects", fr: "Projets" },
  { id: "models", icon: Boxes, en: "Models", fr: "Modèles" },
  { id: "science", icon: FlaskConical, en: "Science", fr: "Science" },
  { id: "artifacts", icon: FileStack, en: "Artifacts", fr: "Artefacts" },
  { id: "automations", icon: CalendarClock, en: "Scheduled", fr: "Planifié" },
  { id: "plugins", icon: Puzzle, en: "Plugins", fr: "Plugins" },
  { id: "mcp", icon: Cable, en: "MCP", fr: "MCP" },
  { id: "skills", icon: Library, en: "Skills", fr: "Skills" },
  { id: "extensions", icon: Puzzle, en: "Extensions", fr: "Extensions" },
  { id: "compute", icon: Cpu, en: "Compute", fr: "Calcul" },
  { id: "kernel", icon: TerminalSquare, en: "Kernel", fr: "Kernel" },
  { id: "settings", icon: Settings, en: "Settings", fr: "Réglages" },
];

const primaryNavigation = navigation.filter(item => ["chat", "workspaces", "models", "science", "automations", "plugins"].includes(item.id));
const secondaryNavigation = navigation.filter(item => ["artifacts", "mcp", "skills", "extensions", "compute", "kernel"].includes(item.id));

export function App() {
  const [surface, setSurface] = useState<Surface>("chat");
  const [language, setLanguage] = useState<Language>(() => localStorage.getItem("frontier-language") === "fr" ? "fr" : "en");
  const [theme, setTheme] = useState<Theme>(() => localStorage.getItem("frontier-theme") === "light" ? "light" : "dark");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [moreNavigationOpen, setMoreNavigationOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState<DesktopNotification[]>([]);
  const [inspectorOpen, setInspectorOpen] = useState(false);
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
  const showInspector = inspectorOpen && surface === "chat" && activeProjects.length > 0;
  const secondarySurfaceActive = secondaryNavigation.some(item => item.id === surface);

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
      const desktopRuntime = "__TAURI_INTERNALS__" in window;
      setWorkspaceError(
        desktopRuntime && reason instanceof Error
          ? reason.message
          : (language === "fr"
            ? "Les projets locaux sont disponibles dans l'application desktop Shoko's LLM."
            : "Local projects are available in the Shoko's LLM desktop app."),
      );
    }
  }

  async function refreshNotifications() {
    try { setNotifications((await invoke<{ notifications: DesktopNotification[] }>("desktop_notifications_development")).notifications); }
    catch { setNotifications([]); }
  }

  async function acknowledgeNotification(notificationId: string) {
    try { setNotifications((await invoke<{ notifications: DesktopNotification[] }>("acknowledge_desktop_notification_development", { notificationId })).notifications); }
    catch { await refreshNotifications(); }
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
    void refreshNotifications();
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
    <div className={"app-frame" + (sidebarOpen ? "" : " sidebar-collapsed") + (showInspector ? "" : " inspector-collapsed") + (surface === "science" ? " science-mode" : "") + (surface === "chat" ? " chat-mode" : "")}>
      <aside className="primary-sidebar" aria-label={language === "fr" ? "Navigation principale" : "Primary navigation"}>
        <div className="sidebar-brand">
          <button className="brand-button" type="button" onClick={startNewChat} aria-label={language === "fr" ? "Nouvelle discussion" : "New chat"}>
            <span className="brand-glyph"><Command size={17} /></span>
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
          {primaryNavigation.map(item => <NavigationButton key={item.id} item={item} language={language} current={surface} onSelect={setSurface} />)}
          <button className="nav-button secondary-navigation-toggle" type="button" onClick={() => setMoreNavigationOpen(value => !value)} aria-expanded={moreNavigationOpen} aria-controls="secondary-navigation" aria-current={secondarySurfaceActive ? "page" : undefined}>
            <ChevronRight size={16} className={moreNavigationOpen ? "rotate-90" : undefined} />
            <span>{language === "fr" ? "Plus d’outils" : "More tools"}</span>
          </button>
          {(moreNavigationOpen || secondarySurfaceActive) && <div id="secondary-navigation" className="sidebar-secondary-nav" aria-label={language === "fr" ? "Outils supplémentaires" : "Additional tools"}>
            {secondaryNavigation.map(item => <NavigationButton key={item.id} item={item} language={language} current={surface} onSelect={setSurface} />)}
          </div>}
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

        <div className="sidebar-footer">
          <button className="nav-button" type="button" onClick={() => setSurface("settings")} aria-current={surface === "settings" ? "page" : undefined}><Settings size={16} /><span>{language === "fr" ? "Réglages" : "Settings"}</span></button>
          <div className="sidebar-boundary"><ShieldCheck size={15} /><span>{language === "fr" ? "Local par défaut" : "Local by default"}</span></div>
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
            <div className="notification-menu">
              <button className="icon-button notification-trigger" type="button" onClick={() => { setNotificationsOpen(value => !value); if (!notificationsOpen) void refreshNotifications(); }} aria-label={language === "fr" ? "Notifications" : "Notifications"} aria-expanded={notificationsOpen}>
                <Bell size={17} />
                {notifications.length > 0 && <span className="notification-count">{notifications.length}</span>}
              </button>
              {notificationsOpen && <section className="notification-panel" aria-label={language === "fr" ? "Notifications en attente" : "Pending notifications"}><div className="notification-panel-heading"><strong>{language === "fr" ? "Notifications" : "Notifications"}</strong><button className="minor-action" type="button" onClick={() => void refreshNotifications()}>{language === "fr" ? "Actualiser" : "Refresh"}</button></div>{notifications.length ? notifications.map(notification => <article className={`notification-row notification-${notification.severity}`} key={notification.id}><strong>{notification.title}</strong><p>{notification.body}</p><code>{notification.deep_link}</code><button className="minor-action" type="button" onClick={() => void acknowledgeNotification(notification.id)}>{language === "fr" ? "Acquitter" : "Acknowledge"}</button></article>) : <p className="notification-empty">{language === "fr" ? "Aucune notification en attente." : "No pending notifications."}</p>}</section>}
            </div>
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
            {surface === "plugins" && <PluginHubSurface language={language} projects={projectRecords} />}
            {surface === "mcp" && <RegistrySurface kind="connectors" language={language} projects={projectRecords} />}
            {surface === "skills" && <RegistrySurface kind="skills" language={language} projects={projectRecords} />}
            {surface === "extensions" && <RegistrySurface kind="extensions" language={language} projects={projectRecords} />}
            {surface === "compute" && <ComputeSurface />}
            {surface === "kernel" && <KernelSurface projects={projectRecords} />}
            {surface === "settings" && <SettingsSurface />}
          </section>

          {showInspector && (
            <ProjectContextPanel language={language} project={activeProjects[0] ?? null} report={report} engineStatus={engineReport?.status ?? null} onClose={() => setInspectorOpen(false)} />
          )}
        </div>
      </main>
    </div>
  );
}

function ProjectContextPanel({ language, project, report, engineStatus, onClose }: { language: Language; project: ProjectRecord | null; report: CapabilityReport | null; engineStatus: string | null; onClose: () => void }) {
  const [activity, setActivity] = useState<AgentActivity | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [git, setGit] = useState<GitContext | null>(null);
  useEffect(() => {
    if (!project) { setActivity(null); setArtifacts([]); setGit(null); return; }
    void invoke<AgentActivity>("local_agent_activity_development", { projectId: project.id }).then(setActivity).catch(() => setActivity(null));
    void invoke<{ artifacts: ArtifactRecord[] }>("project_artifacts_development", { projectId: project.id }).then(result => setArtifacts(result.artifacts)).catch(() => setArtifacts([]));
    void invoke<GitContext>("project_git_context_development", { projectId: project.id }).then(setGit).catch(() => setGit(null));
  }, [project?.id]);
  const completedTodos = activity?.todos.filter(todo => todo.state === "completed").length ?? 0;
  const totalTodos = activity?.todos.length ?? 0;
  const progress = totalTodos ? Math.round(completedTodos / totalTodos * 100) : 0;
  return <aside className="context-panel project-context" aria-label={language === "fr" ? "Environnement du projet" : "Project environment"}>
    <div className="context-header"><div><p className="context-kicker">{language === "fr" ? "Environnement" : "Environment"}</p><h2>{project?.name ?? (language === "fr" ? "Aucun projet" : "No project")}</h2></div><button className="icon-button" type="button" onClick={onClose} aria-label={language === "fr" ? "Fermer le contexte" : "Close context"}><ChevronRight size={17} /></button></div>
    {totalTodos > 0 && <section className="context-section"><div className="context-section-title"><ListTodo size={14} /><span>Todos</span><small>{completedTodos}/{totalTodos}</small></div><progress max="100" value={progress} /><ul className="context-todos">{activity?.todos.slice(0, 5).map(todo => <li key={todo.id} data-state={todo.state}><span />{todo.text}</li>)}</ul></section>}
    {git?.repository && <section className="context-section"><div className="context-section-title"><GitBranch size={14} /><span>{git.branch}</span><small>{git.changes ?? 0} {language === "fr" ? "modif." : "changes"}</small></div>{git.ci?.available && git.ci.latest && <p>CI: {git.ci.latest.name} · {git.ci.latest.conclusion || git.ci.latest.status}</p>}</section>}
    {(artifacts.length > 0 || (activity?.tool_calls.length ?? 0) > 0) && <section className="context-section context-stats">{artifacts.length > 0 && <div><FileStack size={14} /><span>Sources</span><strong>{artifacts.length}</strong></div>}{(activity?.tool_calls.length ?? 0) > 0 && <div><Gauge size={14} /><span>{language === "fr" ? "Outils" : "Tools"}</span><strong>{activity?.tool_calls.length}</strong></div>}</section>}
    {activity?.plan && <section className="context-section"><div className="context-section-title"><Code2 size={14} /><span>Plan</span></div><p>{activity.plan}</p></section>}
    <div className="context-runtime"><span>{engineStatus ?? (language === "fr" ? "Moteur en vérification" : "Checking engine")}</span><span>{report ? `${report.operatingSystem} · ${report.logicalCores} CPU` : "Local"}</span></div>
  </aside>;
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
  action?: "doctor" | "clear" | "fast" | "extended" | "plan" | "read" | "ask" | "full";
};

const slashCommands: SlashCommand[] = [
  { name: "/new", icon: Plus, en: "Clear the current draft and output", fr: "Effacer le brouillon et la sortie", action: "clear" },
  { name: "/projects", icon: FolderKanban, en: "Open local projects", fr: "Ouvrir les projets locaux", target: "workspaces" },
  { name: "/models", icon: Boxes, en: "Open model management", fr: "Ouvrir la gestion des modèles", target: "models" },
  { name: "/scheduled", icon: CalendarClock, en: "Open scheduled pipelines", fr: "Ouvrir les pipelines planifiés", target: "automations" },
  { name: "/automations", icon: Workflow, en: "Open local AI pipelines", fr: "Ouvrir les pipelines IA locaux", target: "automations" },
  { name: "/plugins", icon: Puzzle, en: "Open connected capabilities", fr: "Ouvrir les capacités connectées", target: "plugins" },
  { name: "/mcp", icon: Cable, en: "Inspect MCP connectors", fr: "Inspecter les connecteurs MCP", target: "mcp" },
  { name: "/skills", icon: Library, en: "Inspect installed skills", fr: "Inspecter les skills installés", target: "skills" },
  { name: "/extensions", icon: Puzzle, en: "Inspect executable extensions", fr: "Inspecter les extensions exécutables", target: "extensions" },
  { name: "/science", icon: FlaskConical, en: "Open the science workbench", fr: "Ouvrir l’espace Science", target: "science" },
  { name: "/fast", icon: Gauge, en: "Use compact reasoning", fr: "Utiliser le raisonnement rapide", action: "fast" },
  { name: "/deep", icon: Gauge, en: "Use extended reasoning", fr: "Utiliser le raisonnement approfondi", action: "extended" },
  { name: "/plan", icon: ListTodo, en: "Draft an explicit plan before execution", fr: "Préparer un plan explicite avant exécution", action: "plan" },
  { name: "/read", icon: ShieldCheck, en: "Restrict the agent to read access", fr: "Limiter l'agent à la lecture", action: "read" },
  { name: "/ask", icon: ShieldCheck, en: "Ask before protected actions", fr: "Demander avant les actions protégées", action: "ask" },
  { name: "/full", icon: ShieldCheck, en: "Allow full project access", fr: "Autoriser l'accès complet au projet", action: "full" },
  { name: "/doctor", icon: ShieldCheck, en: "Run the local engine diagnostic", fr: "Exécuter le diagnostic du moteur local", action: "doctor" },
  { name: "/settings", icon: Settings, en: "Open application settings", fr: "Ouvrir les réglages", target: "settings" },
];

const frenchCommandDescriptions: Record<string, string> = {
  "/new": "Effacer le brouillon et la sortie", "/projects": "Ouvrir les projets locaux", "/models": "Ouvrir la gestion des modèles", "/scheduled": "Ouvrir les pipelines planifiés", "/automations": "Ouvrir les pipelines IA locaux", "/plugins": "Ouvrir les capacités connectées", "/mcp": "Inspecter les connecteurs MCP", "/skills": "Inspecter les skills installés", "/extensions": "Inspecter les extensions exécutables", "/science": "Ouvrir l'espace Science", "/fast": "Utiliser le raisonnement rapide", "/deep": "Utiliser le raisonnement approfondi", "/plan": "Préparer un plan explicite avant exécution", "/read": "Limiter l'agent à la lecture", "/ask": "Demander avant les actions protégées", "/full": "Autoriser l'accès complet au projet", "/doctor": "Exécuter le diagnostic du moteur local", "/settings": "Ouvrir les réglages",
};

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
  const [palette, setPalette] = useState<"commands" | "resources" | null>(null);
  const [availableSkills, setAvailableSkills] = useState<RegistryEntry[]>([]);
  const [skillId, setSkillId] = useState("");
  const [catalog, setCatalog] = useState<LocalModelCatalog | null>(null);
  const [accessMode, setAccessMode] = useState("ask");
  const [reasoningEffort, setReasoningEffort] = useState("standard");
  const [workMode, setWorkMode] = useState<"chat" | "plan">("chat");

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

  useEffect(() => {
    void invoke<LocalModelCatalog>("local_model_catalog_development")
      .then(result => {
        setCatalog(result);
        setModel(current => current || (result.shoko_gguf.available && result.lm_studio_library.models[0] ? `gguf:${result.lm_studio_library.models[0].path}` : result.ollama.models[0] || ""));
      })
      .catch(() => setCatalog(null));
  }, []);

  const filteredCommands = useMemo(() => {
    const query = prompt.startsWith("/") ? prompt.toLowerCase() : "";
    return slashCommands.filter(command => command.name.startsWith(query));
  }, [prompt]);
  const filteredSkills = useMemo(() => {
    const query = prompt.startsWith("$") ? prompt.slice(1).toLowerCase() : "";
    return availableSkills.filter(skill => `${skill.name ?? ""} ${skill.id}`.toLowerCase().includes(query));
  }, [availableSkills, prompt]);

  async function refreshActivity(nextProjectId = projectId) {
    if (!nextProjectId) return;
    try {
      setActivity(await invoke<AgentActivity>("local_agent_activity_development", { projectId: nextProjectId }));
    } catch {
      setActivity(null);
    }
  }

  async function runCommand(command: SlashCommand) {
    setPalette(null);
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
      setWorkMode("chat");
      return;
    }
    if (command.action === "fast" || command.action === "extended") {
      setReasoningEffort(command.action === "fast" ? "compact" : "extended");
      return;
    }
    if (command.action === "read" || command.action === "ask" || command.action === "full") {
      setAccessMode(command.action);
      return;
    }
    if (command.action === "plan") {
      setReasoningEffort("extended");
      setWorkMode("plan");
      setPrompt(language === "fr" ? "Prépare un plan vérifiable étape par étape avant toute exécution. " : "Prepare a verifiable step-by-step plan before execution. ");
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
      const result = await invoke<{ output: string }>("run_local_agent_development", { projectId, model: model.trim(), prompt: trimmedPrompt, skillIds: skillId ? [skillId] : [], accessMode, reasoningEffort, workMode });
      setOutput(result.output);
      await refreshActivity(projectId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "FR-AGENT-RUN-FAILED");
      await refreshActivity(projectId);
    } finally {
      setBusy(false);
    }
  }

  async function manageTodo(todoId: string, operation: string, todoText?: string) {
    if (!projectId) return;
    await invoke("local_agent_activity_development", { projectId, todoId, operation, todoText });
    await refreshActivity(projectId);
  }

  async function manageGoal(operation: string, todoText?: string) {
    if (!projectId) return;
    await invoke("local_agent_activity_development", { projectId, operation, todoText });
    await refreshActivity(projectId);
  }

  return (
    <section className="chat-workspace">
      <div className="chat-transcript" aria-live="polite">
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

        {activity && (activity.plan || activity.todos.length > 0 || activity.tool_calls.length > 0) && (
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

      {activity?.plan && <section className="activity-ledger"><div className="activity-heading"><Code2 size={16} /><h3>{language === "fr" ? "Gérer l’objectif" : "Manage goal"}</h3></div><div className="workspace-row"><span>{activity.plan_state ?? "active"}: {activity.plan}</span><button type="button" className="minor-action" onClick={() => void manageGoal(activity.plan_state === "paused" ? "goal-active" : "goal-paused")}>{activity.plan_state === "paused" ? (language === "fr" ? "Reprendre" : "Resume") : (language === "fr" ? "Pause" : "Pause")}</button><button type="button" className="minor-action" onClick={() => void manageGoal("goal-completed")}>{language === "fr" ? "Terminer" : "Complete"}</button><button type="button" className="minor-action" onClick={() => void manageGoal("goal-delete")}>{language === "fr" ? "Supprimer" : "Delete"}</button></div><button type="button" className="minor-action" onClick={() => { const next = window.prompt(language === "fr" ? "Modifier l’objectif" : "Edit goal", activity.plan ?? ""); if (next !== null) void manageGoal("goal-update", next); }}>{language === "fr" ? "Modifier l’objectif" : "Edit goal"}</button></section>}

      {activity && activity.todos.length > 0 && <section className="activity-ledger"><div className="activity-heading"><ListTodo size={16} /><h3>{language === "fr" ? "Gérer les todos" : "Manage todos"}</h3></div>{activity.todos.map(todo => <div className="workspace-row" key={todo.id}><span>{todo.state}: {todo.text}</span><button type="button" className="minor-action" onClick={() => void manageTodo(todo.id, todo.state === "paused" ? "pending" : "paused")}>{todo.state === "paused" ? (language === "fr" ? "Reprendre" : "Resume") : (language === "fr" ? "Pause" : "Pause")}</button><button type="button" className="minor-action" onClick={() => void manageTodo(todo.id, "completed")}>{language === "fr" ? "Terminer" : "Complete"}</button><button type="button" className="minor-action" onClick={() => void manageTodo(todo.id, "delete")}>{language === "fr" ? "Supprimer" : "Delete"}</button></div>)}</section>}

      {activity && activity.todos.length > 0 && <div className="todo-edit-list">{activity.todos.map(todo => <button key={`edit-${todo.id}`} className="minor-action" type="button" onClick={() => { const next = window.prompt(language === "fr" ? "Modifier le todo" : "Edit todo", todo.text); if (next !== null) void manageTodo(todo.id, "update", next); }}>{language === "fr" ? `Modifier: ${todo.text}` : `Edit: ${todo.text}`}</button>)}</div>}

      <form className="chat-composer" onSubmit={event => void submit(event)}>
        {palette === "commands" && (
          <div className="command-palette" role="listbox" aria-label={language === "fr" ? "Commandes slash" : "Slash commands"}>
            <div className="command-title"><Command size={15} /><span>{language === "fr" ? "Commandes" : "Commands"}</span><kbd>Esc</kbd></div>
            {filteredCommands.map(command => {
              const CommandIcon = command.icon;
              return (
                <button key={command.name} type="button" onClick={() => void runCommand(command)}>
                  <CommandIcon size={15} />
                  <span><strong>{command.name}</strong><small>{language === "fr" ? frenchCommandDescriptions[command.name] : command.en}</small></span>
                </button>
              );
            })}
            {filteredCommands.length === 0 && <p>{language === "fr" ? "Aucune commande correspondante" : "No matching command"}</p>}
          </div>
        )}
        {palette === "resources" && (
          <div className="command-palette" role="listbox" aria-label={language === "fr" ? "Skills disponibles" : "Available skills"}>
            <div className="command-title"><Library size={15} /><span>Skills</span><kbd>Esc</kbd></div>
            <button type="button" onClick={() => { setSkillId(""); setPrompt(""); setPalette(null); }}><Library size={15} /><span><strong>{language === "fr" ? "Sans skill" : "No skill"}</strong><small>{language === "fr" ? "Retirer le skill sélectionné" : "Clear the selected skill"}</small></span></button>
            {filteredSkills.map(skill => <button key={skill.id} type="button" onClick={() => { setSkillId(skill.id); setPrompt(""); setPalette(null); }}><Library size={15} /><span><strong>${skill.name ?? skill.id}</strong><small>{skill.description ?? skill.id}</small></span></button>)}
          </div>
        )}
        <div className="composer-project-row"><FolderKanban size={14} /><select value={projectId} onChange={event => setProjectId(event.target.value)} aria-label={language === "fr" ? "Projet" : "Project"} disabled={activeProjects.length === 0}>{activeProjects.length === 0 && <option value="">{language === "fr" ? "Aucun projet actif" : "No active project"}</option>}{activeProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select>{skillId && <button type="button" onClick={() => setSkillId("")} className="composer-skill-chip">${availableSkills.find(skill => skill.id === skillId)?.name ?? skillId}</button>}</div>
        <textarea
          value={prompt}
          onChange={event => { const value = event.target.value; setPrompt(value); setPalette(value.startsWith("/") ? "commands" : value.startsWith("$") ? "resources" : null); }}
          onKeyDown={event => { if (event.key === "Escape") setPalette(null); }}
          placeholder={language === "fr" ? "Demandez une modification, tapez / pour une commande ou $ pour un skill" : "Ask for a change, type / for commands or $ for a skill"}
          rows={3}
        />
        <div className="composer-toolbar">
          <div className="composer-tools-left">
            <button className="composer-tool composer-symbol" type="button" onClick={() => { setPrompt("/"); setPalette("commands"); }} aria-label={language === "fr" ? "Ouvrir les commandes" : "Open commands"}>/</button>
            <button className="composer-tool composer-symbol" type="button" onClick={() => { setPrompt("$"); setPalette("resources"); }} aria-label={language === "fr" ? "Choisir un skill" : "Choose a skill"}>$</button>
            <label className="composer-select"><Boxes size={14} /><select value={model} onChange={event => setModel(event.target.value)} aria-label={language === "fr" ? "Modèle local" : "Local model"}><option value="">{language === "fr" ? "Choisir un modèle" : "Choose model"}</option>{catalog?.shoko_gguf.available && catalog.lm_studio_library.models.map(item => <option value={`gguf:${item.path}`} key={item.path}>{item.display_name}</option>)}{catalog?.ollama.models.map(item => <option value={item} key={item}>{item}</option>)}</select></label>
            <label className="composer-select"><ShieldCheck size={14} /><select value={accessMode} onChange={event => setAccessMode(event.target.value)} aria-label={language === "fr" ? "Accès de l’IA" : "AI access"}><option value="read">{language === "fr" ? "Lecture" : "Read"}</option><option value="ask">{language === "fr" ? "Demander" : "Ask"}</option><option value="full">{language === "fr" ? "Accès complet" : "Full access"}</option></select></label>
            <label className="composer-select"><Gauge size={14} /><select value={reasoningEffort} onChange={event => setReasoningEffort(event.target.value)} aria-label={language === "fr" ? "Effort de raisonnement" : "Reasoning effort"}><option value="compact">{language === "fr" ? "Rapide" : "Fast"}</option><option value="standard">Standard</option><option value="extended">{language === "fr" ? "Approfondi" : "Extended"}</option></select></label>
            {workMode === "plan" && <button className="composer-skill-chip" type="button" onClick={() => setWorkMode("chat")}>{language === "fr" ? "Mode plan" : "Plan mode"}</button>}
          </div>
          <button className="send-button" type="submit" disabled={busy || (!prompt.trim().startsWith("/") && (!projectId || !model.trim() || !prompt.trim()))} aria-label={language === "fr" ? "Exécuter" : "Run"}>
            <Send size={16} />
          </button>
        </div>
        {catalog?.lm_studio_library.available && <button className="composer-library-note" type="button" onClick={() => onNavigate("models")}>{catalog.lm_studio_library.models.length} {catalog.shoko_gguf.available ? (language === "fr" ? "modèles GGUF prêts dans le moteur Shoko" : "GGUF models ready in the Shoko engine") : catalog.shoko_gguf.reason === "FR-SHOKO-GGUF-RUNTIME-WINDOWS-INTEGRITY-BLOCKED" ? (language === "fr" ? "GGUF détectés, runtime bloqué par l'intégrité Windows" : "GGUF files found, runtime blocked by Windows integrity") : (language === "fr" ? "GGUF détectés, installez le moteur Shoko pour les exécuter" : "GGUF files found, install the Shoko engine to run them")}</button>}
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

function PluginHubSurface({ language, projects }: { language: Language; projects: ProjectRecord[] | null }) {
  const [kind, setKind] = useState<"connectors" | "skills" | "extensions">("connectors");
  return <section className="plugin-hub">
    <header className="plugin-hub-header">
      <div><p>{language === "fr" ? "CAPACITÉS CONNECTÉES" : "CONNECTED CAPABILITIES"}</p><h2>Plugins</h2></div>
      <div className="plugin-hub-tabs" role="group" aria-label={language === "fr" ? "Type de plugin" : "Plugin type"}>
        <button type="button" aria-pressed={kind === "connectors"} onClick={() => setKind("connectors")}><Cable size={14} />MCP</button>
        <button type="button" aria-pressed={kind === "skills"} onClick={() => setKind("skills")}><Library size={14} />Skills</button>
        <button type="button" aria-pressed={kind === "extensions"} onClick={() => setKind("extensions")}><Puzzle size={14} />Extensions</button>
      </div>
    </header>
    <RegistrySurface kind={kind} language={language} projects={projects} />
  </section>;
}

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
  const [panel, setPanel] = useState<"notebook" | "evidence" | "artifacts">("notebook");
  const activeProjects = projects?.filter(project => project.archived_at === null) ?? [];
  const projectLabel = activeProjects[0]?.name ?? (language === "fr" ? "Projet scientifique local" : "Local science project");
  return (
    <section className="science-workbench">
      <div className="science-titlebar">
        <div className="science-document-title"><FolderKanban size={15} /><div><h2>{projectLabel}</h2><p>{language === "fr" ? "Notebook, artefacts et preuves du projet" : "Project notebook, artifacts, and evidence"}</p></div></div>
        <div className="science-panel-switch" role="group" aria-label={language === "fr" ? "Vue scientifique" : "Science view"}>
          <button type="button" aria-pressed={panel === "notebook"} onClick={() => setPanel("notebook")}><Code2 size={15} />Notebook</button>
          <button type="button" aria-pressed={panel === "evidence"} onClick={() => setPanel("evidence")}><FlaskConical size={15} />{language === "fr" ? "Preuves" : "Evidence"}</button>
          <button type="button" aria-pressed={panel === "artifacts"} onClick={() => setPanel("artifacts")}><FileStack size={15} />{language === "fr" ? "Artefacts" : "Artifacts"}</button>
        </div>
        <div className="science-boundary"><ShieldCheck size={14} /><span>{language === "fr" ? "Local" : "Local"}</span></div>
      </div>
      <div className="science-view">
        {panel === "notebook" && <ScienceNotebookSurface projects={projects} language={language} />}
        {panel === "evidence" && <div className="science-evidence-view"><ScienceSurface /><ReviewerSurface /></div>}
        {panel === "artifacts" && <div className="science-evidence-view"><ArtifactsSurface /><AnnotationSurface /></div>}
      </div>
    </section>
  );
}

function ScienceNotebookSurface({ projects, language }: { projects: ProjectRecord[] | null; language: Language }) {
  const activeProjects = projects?.filter(project => project.archived_at === null) ?? [];
  return <div className="science-notebook-view">
    <aside className="science-notebook-context">
      <div className="surface-mark">{language === "fr" ? "SESSION" : "SESSION"}</div>
      <h3>{language === "fr" ? "Notebook du projet" : "Project notebook"}</h3>
      <p>{language === "fr" ? "Le code, les sorties et les artefacts restent liés au projet sélectionné." : "Code, output, and artifacts remain attached to the selected project."}</p>
      <div className="science-project-list">
        {activeProjects.map(project => <div key={project.id}><FolderKanban size={14} /><span>{project.name}</span></div>)}
        {activeProjects.length === 0 && <div><CircleAlert size={14} /><span>{language === "fr" ? "Créez un projet pour démarrer un kernel." : "Create a project to start a kernel."}</span></div>}
      </div>
    </aside>
    <div className="science-notebook-kernel"><KernelSurface projects={projects} /></div>
  </div>;
}

function ReviewerSurface() { const language = localStorage.getItem("frontier-language") === "fr" ? "fr" : "en"; const [findings, setFindings] = useState<Array<{ claim_id: string; code: string; severity: string; message: string }> | null>(null); const [error, setError] = useState<string | null>(null); async function review() { try { setError(null); setFindings((await invoke<{ findings: Array<{ claim_id: string; code: string; severity: string; message: string }> }>("review_scientific_claims_development")).findings); } catch (reason) { setError(reason instanceof Error ? reason.message : surfaceText(language, "reviewer")); } } useEffect(() => { void review(); }, []); return <section className="surface review-panel"><div className="surface-mark">EVIDENCE REVIEW</div><h2>{findings ? `${findings.length} ${surfaceText(language, findings.length === 1 ? "openFindingOne" : "openFindingMany")}` : surfaceText(language, "reviewer")}</h2><p>Findings identify missing evidence. They do not rerun analyses or grant scientific approval.</p>{error && <p className="agent-error">{error}</p>}{findings && <Evidence rows={findings.length ? findings.map(finding => `${finding.severity}: ${finding.code} · claim ${finding.claim_id} · ${finding.message}`) : [surfaceText(language, "noEvidenceGaps")]} />}<button className="action" onClick={() => void review()}>Run evidence review</button></section>; }

function AnnotationSurface() { const language = localStorage.getItem("frontier-language") === "fr" ? "fr" : "en"; const [versionId, setVersionId] = useState(""); const [targetKind, setTargetKind] = useState("text"); const [selector, setSelector] = useState('{"offset":0}'); const [body, setBody] = useState(""); const [annotations, setAnnotations] = useState<Array<{ id: string; target_kind: string; body: string; consumed_at: string | null }> | null>(null); const [error, setError] = useState<string | null>(null); async function load() { try { setError(null); setAnnotations((await invoke<{ annotations: Array<{ id: string; target_kind: string; body: string; consumed_at: string | null }> }>("project_annotations_development", { artifactVersionId: versionId })).annotations); } catch (reason) { setError(reason instanceof Error ? reason.message : surfaceText(language, "annotation")); } } async function create(event: FormEvent) { event.preventDefault(); try { await invoke("create_project_annotation_development", { artifactVersionId: versionId, targetKind, selector, body }); setBody(""); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : surfaceText(language, "annotation")); } } return <section className="surface annotation-panel"><div className="surface-mark">VERSIONED ANNOTATIONS</div><h2>Exact artifact feedback</h2><p>Annotations stay attached to the artifact version you name. A missing version is rejected.</p><form className="project-form" onSubmit={event => void create(event)}><label htmlFor="annotation-version">Artifact version, target, selector, and note</label><input id="annotation-version" value={versionId} onChange={event => setVersionId(event.target.value)} placeholder={surfaceText(language, "artifactVersionId")} required /><select value={targetKind} onChange={event => setTargetKind(event.target.value)}><option value="text">Text</option><option value="code">Code</option><option value="markdown">Markdown</option><option value="latex">LaTeX</option><option value="pdf_region">PDF region</option><option value="image_point">Image point</option><option value="html_element">HTML element</option><option value="transcript_region">Transcript region</option></select><input value={selector} onChange={event => setSelector(event.target.value)} placeholder='{"page":2}' required /><textarea value={body} onChange={event => setBody(event.target.value)} placeholder={surfaceText(language, "annotation")} required /><button className="action" type="submit">Save annotation</button></form>{error && <p className="agent-error">{error}</p>}<button className="minor-action" onClick={() => void load()}>Refresh annotations</button>{annotations && <Evidence rows={annotations.length ? annotations.map(annotation => `${annotation.target_kind}: ${annotation.body}`) : [surfaceText(language, "noOpenAnnotations")]} />}</section>; }

function KernelSurface({ projects }: { projects: ProjectRecord[] | null }) {
  const language = localStorage.getItem("frontier-language") === "fr" ? "fr" : "en";
  const activeProjects = projects?.filter(project => project.archived_at === null) ?? [];
  const [projectId, setProjectId] = useState("");
  const [code, setCode] = useState("");
  const [result, setResult] = useState<KernelResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const next = activeProjects.some(project => project.id === projectId) ? projectId : activeProjects[0]?.id ?? "";
    if (next !== projectId) setProjectId(next);
  }, [projects, projectId]);

  async function execute(event: FormEvent) {
    event.preventDefault();
    if (!projectId || !code.trim()) return;
    setError(null);
    setBusy(true);
    try {
      setResult(await invoke<KernelResult>("kernel_execute_development", { projectId, code }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Kernel execution failed.");
    } finally {
      setBusy(false);
    }
  }

  async function restart() {
    if (!projectId) return;
    setError(null);
    try {
      await invoke("kernel_restart_development", { projectId });
      setResult(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Kernel restart failed.");
    }
  }

  if (activeProjects.length === 0) return <section className="kernel-empty"><Code2 size={22} /><h3>{language === "fr" ? "Créez d'abord un projet" : "Create a project first"}</h3><p>{language === "fr" ? "Le notebook conservera son contexte dans ce projet." : "The notebook will keep its context in that project."}</p></section>;

  return <section className="kernel-workspace">
    <header className="kernel-toolbar">
      <label><span>{language === "fr" ? "Projet" : "Project"}</span><select value={projectId} onChange={event => setProjectId(event.target.value)}>{activeProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
      <span className="kernel-status"><span />Python</span>
      <button className="minor-action" type="button" onClick={() => void restart()}>{language === "fr" ? "Redémarrer" : "Restart"}</button>
    </header>
    <form className="kernel-cell" onSubmit={event => void execute(event)}>
      <div className="kernel-cell-label"><span>In</span><small>Python</small></div>
      <textarea value={code} onChange={event => setCode(event.target.value)} spellCheck={false} placeholder={language === "fr" ? "Écrivez du Python..." : "Write Python..."} required />
      <footer><span>{busy ? (language === "fr" ? "Exécution..." : "Running...") : (language === "fr" ? "Kernel local persistant" : "Persistent local kernel")}</span><button className="action" type="submit" disabled={busy || !code.trim()}><Play size={14} />{language === "fr" ? "Exécuter" : "Run"}</button></footer>
    </form>
    {error && <div className="inline-error" role="alert"><CircleAlert size={16} /><p>{error}</p></div>}
    {result && <section className="kernel-result">
      <header><span>Out</span><small>{result.job.state}</small></header>
      {result.execution.stdout && <pre>{result.execution.stdout}</pre>}
      {result.execution.stderr && <pre className="kernel-stderr">{result.execution.stderr}</pre>}
      {result.execution.error && <pre className="kernel-stderr">{result.execution.error}</pre>}
      {!result.execution.stdout && !result.execution.stderr && !result.execution.error && <p>{language === "fr" ? "Cellule exécutée sans sortie." : "Cell completed without output."}</p>}
    </section>}
  </section>;
}

function AgentSurface({ projects }: { projects: ProjectRecord[] | null }) { const activeProjects = projects?.filter(project => project.archived_at === null) ?? []; const [projectId, setProjectId] = useState(""); const [model, setModel] = useState(""); const [prompt, setPrompt] = useState(""); const [activity, setActivity] = useState<AgentActivity | null>(null); const [output, setOutput] = useState<string | null>(null); const [error, setError] = useState<string | null>(null); useEffect(() => { const nextProjectId = activeProjects.some(project => project.id === projectId) ? projectId : activeProjects[0]?.id ?? ""; if (nextProjectId !== projectId) setProjectId(nextProjectId); }, [projects, projectId]); async function refresh() { if (!projectId) { setActivity(null); return; } setError(null); try { setActivity(await invoke<AgentActivity>("local_agent_activity_development", { projectId })); } catch (reason) { setError(reason instanceof Error ? reason.message : "Agent activity is unavailable."); } } async function run(event: FormEvent) { event.preventDefault(); if (!projectId) return; setError(null); setOutput(null); try { const result = await invoke<{ output: string }>("run_local_agent_development", { projectId, model, prompt }); setOutput(result.output); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Local agent run failed."); await refresh(); } } useEffect(() => { void refresh(); }, [projectId]); return <section className="surface"><div className="surface-mark">LOCAL AGENT</div><h2>{activeProjects.length ? "Plan, output, and tool ledger" : "Create an active project first"}</h2><p>The agent calls only the exact local Ollama model you enter. It does not fall back to another model or provider. Failed runtime checks remain in the project activity ledger.</p>{activeProjects.length > 0 && <><form className="project-form agent-form" onSubmit={event => void run(event)}><label htmlFor="agent-project">Project, installed model, and task</label><select id="agent-project" value={projectId} onChange={event => setProjectId(event.target.value)}>{activeProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select><input value={model} onChange={event => setModel(event.target.value)} placeholder="Installed Ollama model" required /><textarea value={prompt} onChange={event => setPrompt(event.target.value)} placeholder="Local task" required /><button className="action" type="submit">Run local agent</button></form>{error && <p className="agent-error">{error}</p>}{output !== null && <pre className="agent-output">{output}</pre>}{activity && <><div className="agent-ledger"><div><span className="surface-mark">PLAN</span><p>{activity.plan ?? "No durable plan recorded yet."}</p></div><div><span className="surface-mark">TODOS</span><Evidence rows={activity.todos.length ? activity.todos.map(todo => `${todo.state}: ${todo.text}`) : ["No local todo recorded"]} /></div><div><span className="surface-mark">TOOL ACTIVITY</span><Evidence rows={activity.tool_calls.length ? activity.tool_calls.map(call => `${call.created_at || "legacy record"}: ${call.state}: ${call.tool_name} (${call.request.model ?? "no model"})${call.result.error ? `; ${call.result.error}` : ""}`) : ["No local tool call recorded"]} /></div></div><button className="minor-action" onClick={() => void refresh()}>Refresh agent activity</button></>}</>}</section>; }

function WorkspaceSurface({ projects, error, refresh, create: _create }: { projects: ProjectRecord[] | null; error: string | null; refresh: () => Promise<void>; create: (name: string) => Promise<void> }) {
  const language = localStorage.getItem("frontier-language") === "fr" ? "fr" : "en";
  const activeProjects = projects?.filter(project => project.archived_at === null) ?? [];
  const archivedProjects = projects?.filter(project => project.archived_at !== null) ?? [];
  const [selected, setSelected] = useState("");
  const [name, setName] = useState("");
  const [folder, setFolder] = useState("");
  const [instructions, setInstructions] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [sessions, setSessions] = useState<SessionRecord[] | null>(null);
  const [grants, setGrants] = useState<FolderGrant[]>([]);
  const [git, setGit] = useState<GitContext | null>(null);
  const [sessionTitle, setSessionTitle] = useState("");
  const [reasoningEffort, setReasoningEffort] = useState("standard");
  const [message, setMessage] = useState<string | null>(null);
  const activeProject = activeProjects.find(project => project.id === selected) ?? null;

  async function loadProject(projectId: string) {
    const project = activeProjects.find(item => item.id === projectId);
    setSelected(projectId);
    setInstructions(project?.instructions ?? "");
    setSessions(null);
    setMessage(null);
    try {
      const [sessionResult, folderResult, gitResult] = await Promise.all([
        invoke<{ sessions: SessionRecord[] }>("workspace_sessions_development", { projectId }),
        invoke<{ grants: FolderGrant[] }>("project_folders_development", { projectId }),
        invoke<GitContext>("project_git_context_development", { projectId }),
      ]);
      setSessions(sessionResult.sessions);
      setGrants(folderResult.grants.filter(grant => grant.revoked_at === null));
      setGit(gitResult);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Project details are unavailable.");
    }
  }

  useEffect(() => {
    if (activeProjects.length === 0) {
      setSelected("");
      setSessions(null);
      setGrants([]);
      setGit(null);
      return;
    }
    if (!activeProjects.some(project => project.id === selected)) void loadProject(activeProjects[0].id);
  }, [projects]);

  async function submitProject(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    try {
      const created = await invoke<{ id: string }>("create_workspace_project_development", { name, instructions });
      if (folder.trim()) await invoke("grant_project_folder_development", { projectId: created.id, folder: folder.trim(), operation: "write" });
      setName("");
      setFolder("");
      setInstructions("");
      setShowCreate(false);
      await refresh();
      await loadProject(created.id);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Project creation failed.");
    }
  }

  async function updateInstructions() {
    if (!activeProject) return;
    try {
      await invoke("set_workspace_project_instructions_development", { projectId: activeProject.id, instructions });
      await refresh();
      setMessage(language === "fr" ? "Instructions enregistrées." : "Instructions saved.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Project update failed.");
    }
  }

  async function linkFolder(event: FormEvent) {
    event.preventDefault();
    if (!activeProject || !folder.trim()) return;
    try {
      await invoke("grant_project_folder_development", { projectId: activeProject.id, folder: folder.trim(), operation: "write" });
      setFolder("");
      await loadProject(activeProject.id);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Folder linking failed.");
    }
  }

  async function submitSession(event: FormEvent) {
    event.preventDefault();
    if (!activeProject) return;
    try {
      await invoke("create_workspace_session_development", { projectId: activeProject.id, title: sessionTitle, parentSessionId: null, reasoningEffort });
      setSessionTitle("");
      await loadProject(activeProject.id);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Session creation failed.");
    }
  }

  async function toggleStar(session: SessionRecord) {
    await invoke("set_workspace_session_starred_development", { sessionId: session.id, starred: !session.starred });
    if (activeProject) await loadProject(activeProject.id);
  }

  async function archive() {
    if (!activeProject) return;
    await invoke("archive_workspace_project_development", { projectId: activeProject.id });
    setSelected("");
    await refresh();
  }

  async function restore(projectId: string) {
    try {
      await invoke("restore_workspace_project_development", { projectId });
      await refresh();
      setSelected(projectId);
      setMessage(language === "fr" ? "Projet restauré." : "Project restored.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Project restoration failed.");
    }
  }

  return <section className="projects-surface">
    <header className="projects-header">
      <div><h2>{language === "fr" ? "Projets" : "Projects"}</h2><p>{language === "fr" ? "Contexte, discussions et dossiers locaux." : "Context, chats, and local folders."}</p></div>
      <button className="minor-action" type="button" onClick={() => setShowCreate(value => !value)}><Plus size={15} />{language === "fr" ? "Nouveau projet" : "New project"}</button>
    </header>

    {showCreate && <form className="project-create-card" onSubmit={event => void submitProject(event)}>
      <div className="project-form-heading"><strong>{language === "fr" ? "Créer un projet" : "Create a project"}</strong><button className="icon-button" type="button" onClick={() => setShowCreate(false)} aria-label={language === "fr" ? "Fermer" : "Close"}><ChevronLeft size={16} /></button></div>
      <label>{language === "fr" ? "Nom" : "Name"}<input value={name} onChange={event => setName(event.target.value)} autoFocus required /></label>
      <label>{language === "fr" ? "Dossier local, facultatif" : "Local folder, optional"}<input value={folder} onChange={event => setFolder(event.target.value)} placeholder="C:\\Projects\\my-project" /></label>
      <label>{language === "fr" ? "Instructions du projet, facultatif" : "Project instructions, optional"}<textarea value={instructions} onChange={event => setInstructions(event.target.value)} /></label>
      <button className="action" type="submit">{language === "fr" ? "Créer" : "Create"}</button>
    </form>}

    {message && <p className="project-message">{message}</p>}
    <div className="projects-layout">
      <aside className="project-list-pane">
        {projects === null && <p>{error ?? (language === "fr" ? "Chargement..." : "Loading...")}</p>}
        {projects !== null && activeProjects.length === 0 && <div className="project-empty"><FolderKanban size={22} /><strong>{language === "fr" ? "Aucun projet" : "No projects yet"}</strong><p>{language === "fr" ? "Créez un projet pour regrouper vos discussions et fichiers." : "Create a project to group chats and files."}</p></div>}
        {activeProjects.map(project => <button className="project-list-item" aria-current={selected === project.id ? "true" : undefined} key={project.id} type="button" onClick={() => void loadProject(project.id)}><FolderKanban size={15} /><span><strong>{project.name}</strong><small>{new Date(project.created_at).toLocaleDateString()}</small></span></button>)}
        {archivedProjects.length > 0 && <section className="archived-project-list"><small>{language === "fr" ? "Archivés" : "Archived"}</small>{archivedProjects.map(project => <div className="workspace-row" key={project.id}><span>{project.name}</span><button className="minor-action" type="button" onClick={() => void restore(project.id)}>{language === "fr" ? "Restaurer" : "Restore"}</button></div>)}</section>}
      </aside>

      <div className="project-detail-pane">
        {!activeProject && activeProjects.length > 0 && <p>{language === "fr" ? "Sélectionnez un projet." : "Select a project."}</p>}
        {activeProject && <>
          <header className="project-detail-header">
            <div><h3>{activeProject.name}</h3>{grants[0] && <p>{grants[0].path}</p>}</div>
            <button className="minor-action" type="button" onClick={() => void archive()}>{language === "fr" ? "Archiver" : "Archive"}</button>
          </header>

          {git?.repository && <div className="project-git-strip">
            <span><GitBranch size={14} />{git.branch}</span>
            <span>{git.changes ?? 0} {language === "fr" ? "fichiers modifiés" : "changed files"}</span>
            {git.ci?.available && git.ci.latest && <a href={git.ci.latest.url} target="_blank" rel="noreferrer">CI: {git.ci.latest.conclusion || git.ci.latest.status}</a>}
          </div>}

          <section className="project-section">
            <div className="project-section-heading"><div><h4>{language === "fr" ? "Discussions" : "Chats"}</h4><p>{language === "fr" ? "Sessions enregistrées dans ce projet." : "Sessions saved in this project."}</p></div></div>
            <form className="project-session-form" onSubmit={event => void submitSession(event)}>
              <input value={sessionTitle} onChange={event => setSessionTitle(event.target.value)} placeholder={language === "fr" ? "Nom de la discussion" : "Chat name"} required />
              <select value={reasoningEffort} onChange={event => setReasoningEffort(event.target.value)}><option value="compact">{language === "fr" ? "Rapide" : "Fast"}</option><option value="standard">Standard</option><option value="extended">{language === "fr" ? "Approfondi" : "Extended"}</option></select>
              <button className="minor-action" type="submit"><Plus size={14} />{language === "fr" ? "Ajouter" : "Add"}</button>
            </form>
            <div className="project-session-list">
              {sessions?.map(session => <div key={session.id}><MessageSquare size={14} /><span><strong>{session.title}</strong><small>{session.reasoning_effort}</small></span><button className="icon-button" type="button" onClick={() => void toggleStar(session)} aria-label={session.starred ? "Unstar" : "Star"}><Star size={14} fill={session.starred ? "currentColor" : "none"} /></button></div>)}
              {sessions?.length === 0 && <p>{language === "fr" ? "Aucune discussion enregistrée." : "No saved chats."}</p>}
            </div>
          </section>

          <details className="project-settings">
            <summary><Settings size={14} />{language === "fr" ? "Réglages du projet" : "Project settings"}</summary>
            <label>{language === "fr" ? "Instructions" : "Instructions"}<textarea value={instructions} onChange={event => setInstructions(event.target.value)} /></label>
            <button className="minor-action" type="button" onClick={() => void updateInstructions()}>{language === "fr" ? "Enregistrer" : "Save"}</button>
            <form onSubmit={event => void linkFolder(event)}>
              <label>{language === "fr" ? "Ajouter un dossier local" : "Add a local folder"}<input value={folder} onChange={event => setFolder(event.target.value)} placeholder="C:\\Projects\\my-project" required /></label>
              <button className="minor-action" type="submit">{language === "fr" ? "Lier le dossier" : "Link folder"}</button>
            </form>
          </details>
        </>}
      </div>
    </div>
  </section>;
}
function ScienceSurface() { const [queries, setQueries] = useState<Array<{ id: string; query_text: string; source: string; result_count: number; accessed_at: string }> | null>(null); const [claims, setClaims] = useState<ClaimRecord[] | null>(null); const [query, setQuery] = useState(""); const [source, setSource] = useState("local fixture"); const [count, setCount] = useState("0"); const [claimType, setClaimType] = useState("observation"); const [claimText, setClaimText] = useState(""); const [uncertainty, setUncertainty] = useState(""); const [evidenceUri, setEvidenceUri] = useState(""); const [evidenceSelector, setEvidenceSelector] = useState(""); const [error, setError] = useState<string | null>(null); async function refresh() { try { setQueries((await invoke<{ queries: Array<{ id: string; query_text: string; source: string; result_count: number; accessed_at: string }> }>("literature_queries_development")).queries); } catch (reason) { setError(reason instanceof Error ? reason.message : "Literature ledger unavailable."); } } async function refreshClaims() { try { setClaims((await invoke<{ claims: ClaimRecord[] }>("scientific_claims_development")).claims); } catch (reason) { setError(reason instanceof Error ? reason.message : "Scientific claims ledger unavailable."); } } async function submit(event: FormEvent) { event.preventDefault(); try { await invoke("record_literature_query_development", { query, source, resultCount: Number(count) }); setQuery(""); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Literature record failed."); } } async function submitClaim(event: FormEvent) { event.preventDefault(); try { await invoke("create_scientific_claim_development", { claimType, claimText, uncertainty, evidenceUri, evidenceSelector }); setClaimText(""); setUncertainty(""); setEvidenceUri(""); setEvidenceSelector(""); await refreshClaims(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Scientific claim creation failed."); } } async function setClaimStatus(claimId: string, claimStatus: ClaimRecord["status"]) { try { await invoke("set_scientific_claim_status_development", { claimId, claimStatus }); await refreshClaims(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Scientific claim update failed."); } } useEffect(() => { void refresh(); void refreshClaims(); }, []); return <section className="surface"><div className="surface-mark">RESEARCH RECORD</div><h2>{queries ? `${queries.length} reproducible literature quer${queries.length === 1 ? "y" : "ies"}` : "Literature ledger"}</h2><p>Record the exact query, source, filters, access time, and observed result count. No remote literature connector is configured on this machine.</p><form className="project-form" onSubmit={event => void submit(event)}><label htmlFor="literature-query">Query, source, and result count</label><input id="literature-query" value={query} onChange={event => setQuery(event.target.value)} placeholder="Single-cell quality control" required /><input value={source} onChange={event => setSource(event.target.value)} required /><input type="number" min="0" value={count} onChange={event => setCount(event.target.value)} required /><button className="action" type="submit">Record query</button></form>{error && <p>{error}</p>}<button className="action" onClick={() => void refresh()}>Refresh literature ledger</button>{queries && <Evidence rows={queries.map(item => `${item.query_text} | ${item.source} | ${item.result_count} results`)} />}<div className="claim-ledger"><div className="surface-mark">CLAIM EVIDENCE SPINE</div><h2>{claims ? `${claims.length} scientific claim${claims.length === 1 ? "" : "s"}` : "Scientific claim ledger"}</h2><p>Claims are local records, not conclusions. Their type, uncertainty, status, and exact evidence locator remain inspectable.</p><form className="project-form claim-form" onSubmit={event => void submitClaim(event)}><label htmlFor="claim-text">Type, claim, uncertainty, and evidence locator</label><select value={claimType} onChange={event => setClaimType(event.target.value)}><option value="source">Source</option><option value="observation">Observation</option><option value="computed">Computed</option><option value="inference">Inference</option><option value="hypothesis">Hypothesis</option></select><input id="claim-text" value={claimText} onChange={event => setClaimText(event.target.value)} placeholder="Claim text" required /><input value={uncertainty} onChange={event => setUncertainty(event.target.value)} placeholder="Uncertainty or limitation" required /><input value={evidenceUri} onChange={event => setEvidenceUri(event.target.value)} placeholder="artifact://..." required /><input value={evidenceSelector} onChange={event => setEvidenceSelector(event.target.value)} placeholder="table:row-2" required /><button className="action" type="submit">Record claim</button></form><button className="action" onClick={() => void refreshClaims()}>Refresh claim ledger</button>{claims && <div className="claim-list">{claims.length ? claims.map(claim => <article className="claim-row" key={claim.id}><div className="claim-meta"><span>{claim.claim_type}</span><span>{claim.status}</span></div><strong>{claim.text}</strong><p>Uncertainty: {claim.uncertainty}</p>{claim.evidence.map(item => <code key={`${item.evidence_uri}:${item.selector}`}>{item.evidence_uri} · {item.selector}</code>)}<div><button className="minor-action" onClick={() => void setClaimStatus(claim.id, "supported")}>Mark supported</button><button className="minor-action" onClick={() => void setClaimStatus(claim.id, "disputed")}>Mark disputed</button><button className="minor-action" onClick={() => void setClaimStatus(claim.id, "retracted")}>Retract</button></div></article>) : <p>No local claims yet</p>}</div>}</div></section>; }
function ArtifactsSurface() { const [projectId, setProjectId] = useState(""); const [artifacts, setArtifacts] = useState<ArtifactRecord[] | null>(null); const [name, setName] = useState(""); const [content, setContent] = useState(""); const [searchQuery, setSearchQuery] = useState(""); const [searchResults, setSearchResults] = useState<Array<ArtifactRecord & { latest_version: number | null; latest_content_hash: string | null }> | null>(null); const [versions, setVersions] = useState<Array<{ version: number; content_hash: string; execution_log: Record<string, string> }> | null>(null); const [error, setError] = useState<string | null>(null); async function load() { try { setArtifacts((await invoke<{ artifacts: ArtifactRecord[] }>("project_artifacts_development", { projectId })).artifacts); } catch (reason) { setError(reason instanceof Error ? reason.message : "Artifact ledger unavailable."); } } async function submit(event: FormEvent) { event.preventDefault(); try { await invoke("create_project_artifact_development", { projectId, name, mediaType: "text/markdown", content }); setName(""); setContent(""); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Artifact creation failed."); } } async function search(event: FormEvent) { event.preventDefault(); try { setError(null); setSearchResults((await invoke<{ artifacts: Array<ArtifactRecord & { latest_version: number | null; latest_content_hash: string | null }> }>("search_project_artifacts_development", { query: searchQuery, projectId: projectId || null, mediaType: null })).artifacts); } catch (reason) { setError(reason instanceof Error ? reason.message : "Artifact search failed."); } } async function inspect(artifactId: string) { setVersions((await invoke<{ versions: Array<{ version: number; content_hash: string; execution_log: Record<string, string> }> }>("project_artifact_versions_development", { artifactId })).versions); } return <section className="surface"><div className="surface-mark">LINEAGE</div><h2>{artifacts ? `${artifacts.length} versioned artifact${artifacts.length === 1 ? "" : "s"}` : "Artifact ledger"}</h2><p>Payloads are content-addressed and versions retain independent messages and execution-log provenance.</p><form className="project-form" onSubmit={event => void submit(event)}><label htmlFor="artifact-project">Project ID, artifact name, and markdown content</label><input id="artifact-project" value={projectId} onChange={event => setProjectId(event.target.value)} placeholder="Project ID" required /><input value={name} onChange={event => setName(event.target.value)} placeholder="Result name" required /><input value={content} onChange={event => setContent(event.target.value)} placeholder="Markdown content" /><button className="action" type="submit">Save artifact</button></form><form className="project-form" onSubmit={event => void search(event)}><label htmlFor="artifact-search">Literal artifact discovery</label><input id="artifact-search" value={searchQuery} onChange={event => setSearchQuery(event.target.value)} placeholder="Name fragment" required /><button className="minor-action" type="submit">Search artifacts</button></form>{error && <p>{error}</p>}<button className="action" onClick={() => void load()}>Refresh artifacts</button>{searchResults && <Evidence rows={searchResults.length ? searchResults.map(artifact => `${artifact.name} · ${artifact.media_type} · latest v${artifact.latest_version ?? "not saved"}`) : ["No matching artifact names."]} />}{artifacts && <div className="workspace-list">{artifacts.map(artifact => <div className="workspace-row" key={artifact.id}><span>{artifact.name}</span><button className="minor-action" onClick={() => void inspect(artifact.id)}>Inspect versions</button></div>)}</div>}{versions && <Evidence rows={versions.map(version => `v${version.version}: ${version.content_hash.slice(0, 12)}; execution ${version.execution_log.state ?? "recorded"}`)} />}</section>; }
function ComputeSurface() { const [jobs, setJobs] = useState<JobRecord[] | null>(null); const [generations, setGenerations] = useState<GenerationRecord[] | null>(null); const [projectId, setProjectId] = useState(""); const [operation, setOperation] = useState("local.inspect"); const [error, setError] = useState<string | null>(null); async function refresh() { setError(null); try { const [jobResult, generationResult] = await Promise.all([invoke<{ jobs: JobRecord[] }>("compute_jobs_development"), invoke<{ generations: GenerationRecord[] }>("local_generations_development")]); setJobs(jobResult.jobs); setGenerations(generationResult.generations); } catch (reason) { setError(reason instanceof Error ? reason.message : "Compute monitor unavailable."); } } async function submit(event: FormEvent) { event.preventDefault(); try { await invoke("enqueue_compute_job_development", { projectId, operation }); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Job enqueue failed."); } } async function cancel(jobId: string) { await invoke("cancel_compute_job_development", { jobId }); await refresh(); } async function retry(jobId: string) { await invoke("retry_compute_job_development", { jobId }); await refresh(); } useEffect(() => { void refresh(); }, []); return <section className="surface"><div className="surface-mark">SCHEDULER</div><h2>{jobs ? `${jobs.length} durable job${jobs.length === 1 ? "" : "s"}` : "Compute monitor unavailable"}</h2><p>Local jobs retain queued, running, cancellation-requested, cancelled, succeeded, and failed states. No remote host or cloud provider is configured.</p><form className="project-form" onSubmit={event => void submit(event)}><label htmlFor="job-project">Project ID and operation</label><input id="job-project" value={projectId} onChange={event => setProjectId(event.target.value)} placeholder="Project ID" required /><input value={operation} onChange={event => setOperation(event.target.value)} required /><button className="action" type="submit">Queue job</button></form>{error && <p>{error}</p>}{jobs && <div className="workspace-list">{jobs.length ? jobs.map(job => <div className="workspace-row" key={job.id}><span>{job.operation}: {job.state}</span>{["queued", "running"].includes(job.state) && <button className="minor-action" onClick={() => void cancel(job.id)}>Cancel</button>}{["failed", "cancelled"].includes(job.state) && <button className="minor-action" onClick={() => void retry(job.id)}>Retry</button>}</div>) : <p>No jobs queued</p>}</div>}{generations && <Evidence rows={generations.length ? generations.map(generation => `${generation.runtime}/${generation.model}: ${generation.state}; ${generation.output || generation.diagnostic?.code || "no output"}`) : ["No persisted local generations. Install a compatible runtime before creating one."]} />}<button className="action" onClick={() => void refresh()}>Refresh compute monitor</button></section>; }
function SettingsSurface() {
  const [probe, setProbe] = useState<Record<string, unknown> | null>(null);
  const [language, setLanguage] = useState("python");
  const [name, setName] = useState("");
  const [environments, setEnvironments] = useState<EnvironmentRecord[]>([]);
  const [environmentName, setEnvironmentName] = useState("");
  const [packageSpecs, setPackageSpecs] = useState("");
  const [repository, setRepository] = useState("https://cloud.r-project.org");
  const [channel, setChannel] = useState("cran");
  const [networkApproved, setNetworkApproved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function inspect(nextLanguage = language) {
    try {
      const result = await invoke<{ probe: Record<string, unknown>; manifests: EnvironmentRecord[] }>("scientific_environment_probe_development", { language: nextLanguage });
      setProbe(result.probe); setEnvironments(result.manifests); setEnvironmentName(current => result.manifests.some(environment => environment.name === current && environment.language === nextLanguage) ? current : result.manifests.find(environment => environment.language === nextLanguage)?.name ?? "");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Environment probe unavailable."); }
  }
  async function create(event: FormEvent) {
    event.preventDefault(); setError(null);
    try { await invoke("create_python_environment_development", { name }); setName(""); await inspect("python"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Python environment creation failed."); }
  }
  async function install(event: FormEvent) {
    event.preventDefault();
    const packages = packageSpecs.split(",").map(value => value.trim()).filter(Boolean);
    if (!networkApproved || !environmentName || packages.length === 0) return;
    setError(null);
    try {
      if (language === "python") await invoke("install_environment_packages_development", { name: environmentName, packages });
      else await invoke("install_r_environment_packages_development", { name: environmentName, packages, repository, channel });
      setPackageSpecs(""); setNetworkApproved(false); await inspect(language);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Package installation failed."); }
  }
  const visibleEnvironments = environments.filter(environment => environment.language === language);
  useEffect(() => { void inspect(); }, []);
  return <section className="surface"><div className="surface-mark">TRUST BOUNDARY</div><h2>Local environments</h2><p>Create isolated environments locally. Package installation is a separate, approval-gated network action and the resulting package fingerprint remains inspectable.</p><form className="project-form" onSubmit={event => void create(event)}><label htmlFor="environment-name">New local Python environment</label><input id="environment-name" value={name} onChange={event => setName(event.target.value)} placeholder="analysis" pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,63}" required /><button className="action" type="submit">Create Python environment</button></form><div className="workspace-list"><div className="workspace-row"><button className="minor-action" type="button" onClick={() => { setLanguage("python"); void inspect("python"); }}>Probe Python</button><button className="minor-action" type="button" onClick={() => { setLanguage("r"); void inspect("r"); }}>Probe R</button></div></div>{error && <p className="agent-error">{error}</p>}{probe && <dl>{Object.entries(probe).map(([key, value]) => <><dt key={`${key}-term`}>{key}</dt><dd key={`${key}-value`}>{String(value)}</dd></>)}</dl>}{visibleEnvironments.length > 0 && <form className="project-form" onSubmit={event => void install(event)}><label htmlFor="environment-packages">Environment and packages</label><select value={environmentName} onChange={event => setEnvironmentName(event.target.value)} required>{visibleEnvironments.map(environment => <option key={environment.name} value={environment.name}>{environment.name}</option>)}</select><input id="environment-packages" value={packageSpecs} onChange={event => setPackageSpecs(event.target.value)} placeholder={language === "python" ? "numpy==2.0.0, pandas" : "Seurat, ggplot2"} required />{language === "r" && <><select value={channel} onChange={event => setChannel(event.target.value)}><option value="cran">CRAN</option><option value="bioconductor">Bioconductor</option></select><input value={repository} onChange={event => setRepository(event.target.value)} placeholder="https://cloud.r-project.org" required /></>}<label className="approval-check"><input type="checkbox" checked={networkApproved} onChange={event => setNetworkApproved(event.target.checked)} />I approve network access to install these packages.</label><button className="action" type="submit" disabled={!networkApproved || !packageSpecs.trim()}>Install packages</button></form>}{environments.length > 0 && <Evidence rows={environments.map(environment => `${environment.name}: ${environment.python_version ?? environment.runtime_version ?? environment.language}; ${environment.executable ?? "no executable"}; ${environment.package_fingerprint ?? "no fingerprint"}`)} />}<Evidence rows={["Environment creation: no package download", "Provider fallback: forbidden", "Package installs: explicit network approval required"]} /></section>;
}
function Surface({ mark, title, text, rows }: { mark: string; title: string; text: string; rows: string[] }) { return <section className="surface"><div className="surface-mark">{mark}</div><h2>{title}</h2><p>{text}</p><Evidence rows={rows} /></section>; }
function Evidence({ rows }: { rows: string[] }) { return <ul className="evidence">{rows.map(row => <li key={row}><span>verified state</span>{row}</li>)}</ul>; }
