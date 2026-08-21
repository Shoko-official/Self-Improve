import { invoke } from "@tauri-apps/api/core";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { CircleAlert, Cpu, Download, FileCheck2, Gauge, HardDrive, Link2, RefreshCw, Search, ShieldCheck, Square, Thermometer } from "lucide-react";
import type { Language } from "./i18n";

type CapabilityReport = { operatingSystem: string; architecture: string; logicalCores: number; capturedAt: number };
type EngineDoctorReport = { checked_at: string; host: { machine: string; release: string; system: string }; protocol_version: number; status: string };
type ProjectRecord = { id: string; name: string; archived_at: string | null };
type HubModel = { modelId: string; downloads: number | null; likes: number | null; tags: string[] | null };
type TransferPlan = {
  repository_id: string;
  revision: string;
  filename: string;
  url: string;
  destination: string;
  bytes: number | null;
  required_free_bytes: number | null;
  free_bytes: number;
  fits: boolean;
  accelerator: string;
  xet_available: boolean;
  interactive: boolean;
};
type ProgressDetail = { received_bytes: number; total_bytes: number | null; percent: number | null; bytes_per_second: number };
type TransferEvent = { sequence_number: number; kind: string; detail: ProgressDetail };
type ModelTransfer = {
  id: string;
  project_id: string;
  parent_job_id: string | null;
  state: "queued" | "running" | "cancel_requested" | "cancelled" | "succeeded" | "failed";
  request: { repository_id: string; filename: string; destination: string; revision: string; expected_sha256: string | null; plan: TransferPlan };
  result: { transfer: { bytes: number; bytes_per_second: number; method: string; resumed_bytes: number; sha256: string }; model: { path: string; capability_state: string } } | null;
  diagnostic: { code: string; detail?: string } | null;
  events: TransferEvent[];
};
type RuntimeInstallRecord = { id: string; state: string; result: { model: string } | null; diagnostic: { code: string } | null; events: Array<{ sequence_number: number; kind: string; detail: { output?: string } }> };
type InferencePlan = {
  supported: boolean;
  models: string[];
  missing_models: string[];
  options: { num_ctx: number; num_batch: number; num_thread: number; num_gpu?: number };
  keep_alive: string;
  concurrency: number;
  estimated_working_set_bytes: number;
  memory_budget_bytes: number;
  memory_source: "gpu" | "system";
  automatic_cpu_fallback: boolean;
  reasons: string[];
  hardware: { logical_cores: number; system_memory_bytes: number | null; gpu_devices: Array<{ name: string; memory_bytes: number }>; gpu_memory_bytes: number };
};
type WarmupResult = {
  plan: InferencePlan;
  warmup: null | {
    model: string;
    keep_alive: string;
    metrics: { total_duration?: number; load_duration?: number; tokens_per_second?: number };
    loaded: { context_length?: number; size_vram?: number; expires_at?: string };
  };
};
type LibraryModel = { key: string; display_name: string; path: string; size_bytes: number; format: string; execution_runtime: string };
type LmStudioLibrary = { source: string; available: boolean; reason: string | null; models_root: string; models: LibraryModel[] };
type ManagedRuntime = { runtime: string; available: boolean; version: string; path: string | null; reason: string | null; independent_of_lm_studio: boolean };
type RegisteredModel = { path: string; capability_state: string };
type LocalModelCatalog = { shoko_gguf: ManagedRuntime; lm_studio_library: LmStudioLibrary; registered_models: RegisteredModel[] };

export const selectedLocalModelKey = "frontier-selected-local-model";

export function registeredExternalModelPaths(models: RegisteredModel[]): Set<string> {
  return new Set(models.filter(model => model.capability_state === "external-reference").map(model => model.path));
}

type ModelsSurfaceProps = {
  report: CapabilityReport | null;
  error: string | null;
  probe: () => Promise<void>;
  engineReport: EngineDoctorReport | null;
  engineError: string | null;
  probeEngine: () => Promise<void>;
  projects: ProjectRecord[] | null;
  language: Language;
};

const terminalStates = new Set<ModelTransfer["state"]>(["cancelled", "succeeded", "failed"]);

export function formatBytes(value: number | null, language: Language = "en"): string {
  if (value === null) return language === "fr" ? "Inconnu" : "Unknown";
  if (value < 1024) return `${value} B`;
  const units = ["KiB", "MiB", "GiB", "TiB"];
  let size = value / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && size >= 1024; index += 1) {
    size /= 1024;
    unit = units[index];
  }
  return `${size >= 10 ? size.toFixed(1) : size.toFixed(2)} ${unit}`;
}

export function latestProgress(transfer: ModelTransfer | null): ProgressDetail | null {
  if (!transfer) return null;
  const event = [...transfer.events].reverse().find(item => item.kind === "progress");
  return event?.detail ?? null;
}

export function parseOptionalInteger(value: string): number | null {
  return value.trim() === "" ? null : Number.parseInt(value, 10);
}

export function formatNanoseconds(value: number | undefined, language: Language = "en"): string {
  if (value === undefined) return language === "fr" ? "Inconnu" : "Unknown";
  return `${(value / 1_000_000_000).toFixed(2)} s`;
}

export function ModelsSurface({ report, error, probe, engineReport, engineError, probeEngine, projects, language }: ModelsSurfaceProps) {
  const activeProjects = projects?.filter(project => project.archived_at === null) ?? [];
  const [query, setQuery] = useState("");
  const [models, setModels] = useState<HubModel[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [repositoryId, setRepositoryId] = useState("");
  const [filename, setFilename] = useState("");
  const [destination, setDestination] = useState("");
  const [revision, setRevision] = useState("main");
  const [sha256, setSha256] = useState("");
  const [projectId, setProjectId] = useState("");
  const [plan, setPlan] = useState<TransferPlan | null>(null);
  const [planning, setPlanning] = useState(false);
  const [transfer, setTransfer] = useState<ModelTransfer | null>(null);
  const [ollamaModel, setOllamaModel] = useState("");
  const [ollamaInstall, setOllamaInstall] = useState<RuntimeInstallRecord | null>(null);
  const [profileModels, setProfileModels] = useState("");
  const [contextLength, setContextLength] = useState("");
  const [cpuThreads, setCpuThreads] = useState("");
  const [batchSize, setBatchSize] = useState("");
  const [gpuLayers, setGpuLayers] = useState("");
  const [keepAlive, setKeepAlive] = useState("15m");
  const [concurrency, setConcurrency] = useState("1");
  const [inferencePlan, setInferencePlan] = useState<InferencePlan | null>(null);
  const [warmup, setWarmup] = useState<WarmupResult["warmup"]>(null);
  const [inspectingInference, setInspectingInference] = useState(false);
  const [warmingModel, setWarmingModel] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);
  const [view, setView] = useState<"library" | "download" | "performance">("library");
  const [lmStudioLibrary, setLmStudioLibrary] = useState<LmStudioLibrary | null>(null);
  const [managedRuntime, setManagedRuntime] = useState<ManagedRuntime | null>(null);
  const [installingManagedRuntime, setInstallingManagedRuntime] = useState(false);
  const [referencedPaths, setReferencedPaths] = useState<Set<string>>(() => new Set());
  const [referencingPath, setReferencingPath] = useState<string | null>(null);
  const progress = useMemo(() => latestProgress(transfer), [transfer]);
  const isTransferActive = transfer ? !terminalStates.has(transfer.state) : false;
  const destinationExample = report?.operatingSystem === "windows" ? "D:\\Models\\model.gguf" : report?.operatingSystem === "macos" ? "/Users/name/Models/model.gguf" : "/home/name/Models/model.gguf";

  useEffect(() => {
    if (!projectId && activeProjects[0]) setProjectId(activeProjects[0].id);
  }, [activeProjects, projectId]);

  useEffect(() => {
    void invoke<LocalModelCatalog>("local_model_catalog_development")
      .then(result => {
        setLmStudioLibrary(result.lm_studio_library);
        setManagedRuntime(result.shoko_gguf);
        setReferencedPaths(registeredExternalModelPaths(result.registered_models));
      })
      .catch(() => { setLmStudioLibrary(null); setManagedRuntime(null); });
  }, []);

  useEffect(() => {
    if (!transfer || terminalStates.has(transfer.state)) return;
    let disposed = false;
    async function refresh() {
      try {
        const next = await invoke<ModelTransfer>("huggingface_model_transfer_status_development", { jobId: transfer?.id });
        if (!disposed) setTransfer(next);
      } catch (reason) {
        if (!disposed) setModelError(message(reason, language === "fr" ? "Le statut du transfert est indisponible." : "Transfer status is unavailable."));
      }
    }
    const timer = window.setInterval(() => void refresh(), 750);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [language, transfer?.id, transfer?.state]);

  function changeTransferInput(update: () => void) {
    update();
    setPlan(null);
    if (transfer && terminalStates.has(transfer.state)) setTransfer(null);
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    setSearching(true);
    setModelError(null);
    try {
      setModels((await invoke<{ models: HubModel[] }>("search_huggingface_models_development", { query, limit: 10 })).models);
    } catch (reason) {
      setModelError(message(reason, language === "fr" ? "La recherche du catalogue public a échoué." : "Public model search failed."));
    } finally {
      setSearching(false);
    }
  }

  async function inspectTransfer(event: FormEvent) {
    event.preventDefault();
    setPlanning(true);
    setPlan(null);
    setModelError(null);
    try {
      const result = await invoke<{ plan: TransferPlan }>("plan_huggingface_model_download_development", { repositoryId, filename, destination, revision });
      setPlan(result.plan);
    } catch (reason) {
      setModelError(message(reason, language === "fr" ? "Le fichier distant ne peut pas être vérifié." : "The remote file could not be inspected."));
    } finally {
      setPlanning(false);
    }
  }

  async function startTransfer() {
    if (!plan?.fits || !projectId) return;
    setModelError(null);
    try {
      setTransfer(await invoke<ModelTransfer>("start_huggingface_model_transfer_development", { projectId, repositoryId, filename, destination, revision, expectedSha256: sha256 || null }));
    } catch (reason) {
      setModelError(message(reason, language === "fr" ? "Le worker de transfert n'a pas démarré." : "The transfer worker did not start."));
    }
  }

  async function cancelTransfer() {
    if (!transfer) return;
    setModelError(null);
    try {
      setTransfer(await invoke<ModelTransfer>("cancel_huggingface_model_transfer_development", { jobId: transfer.id }));
    } catch (reason) {
      setModelError(message(reason, language === "fr" ? "La demande d'annulation a échoué." : "The cancellation request failed."));
    }
  }

  async function retryTransfer() {
    if (!transfer) return;
    setModelError(null);
    try {
      setTransfer(await invoke<ModelTransfer>("retry_huggingface_model_transfer_development", { jobId: transfer.id }));
    } catch (reason) {
      setModelError(message(reason, language === "fr" ? "La reprise du transfert a échoué." : "The transfer could not resume."));
    }
  }

  async function installOllama(event: FormEvent) {
    event.preventDefault();
    setModelError(null);
    try {
      setOllamaInstall(await invoke<RuntimeInstallRecord>("install_ollama_model_development", { projectId, model: ollamaModel }));
    } catch (reason) {
      setModelError(message(reason, language === "fr" ? "Le téléchargement Ollama n'a pas démarré." : "The Ollama pull did not start."));
    }
  }

  function profileArguments() {
    return {
      models: profileModels.split(",").map(model => model.trim()).filter(Boolean),
      contextLength: parseOptionalInteger(contextLength),
      cpuThreads: parseOptionalInteger(cpuThreads),
      batchSize: parseOptionalInteger(batchSize),
      gpuLayers: parseOptionalInteger(gpuLayers),
      keepAlive,
      concurrency: parseOptionalInteger(concurrency),
    };
  }

  async function inspectInference(event: FormEvent) {
    event.preventDefault();
    setInspectingInference(true);
    setInferencePlan(null);
    setWarmup(null);
    setModelError(null);
    try {
      const result = await invoke<{ plan: InferencePlan }>("ollama_inference_plan_development", profileArguments());
      setInferencePlan(result.plan);
    } catch (reason) {
      setModelError(message(reason, language === "fr" ? "Le profil d'inférence ne peut pas être calculé." : "The inference profile could not be calculated."));
    } finally {
      setInspectingInference(false);
    }
  }

  async function warmupModel() {
    if (!inferencePlan?.supported || inferencePlan.models.length !== 1) return;
    setWarmingModel(true);
    setWarmup(null);
    setModelError(null);
    try {
      const profile = profileArguments();
      const result = await invoke<WarmupResult>("warmup_ollama_model_development", {
        model: inferencePlan.models[0],
        contextLength: profile.contextLength,
        cpuThreads: profile.cpuThreads,
        batchSize: profile.batchSize,
        gpuLayers: profile.gpuLayers,
        keepAlive: profile.keepAlive,
      });
      setWarmup(result.warmup);
      setInferencePlan(result.plan);
    } catch (reason) {
      setModelError(message(reason, language === "fr" ? "Le préchauffage Ollama a échoué." : "Ollama warmup failed."));
    } finally {
      setWarmingModel(false);
    }
  }

  async function referenceLibraryModel(path: string) {
    setReferencingPath(path);
    setModelError(null);
    try {
      await invoke("reference_lm_studio_model_development", { path });
      setReferencedPaths(current => new Set(current).add(path));
      localStorage.setItem(selectedLocalModelKey, `gguf:${path}`);
    } catch (reason) {
      setModelError(message(reason, language === "fr" ? "Le modèle n'a pas pu être référencé." : "The model could not be referenced."));
    } finally {
      setReferencingPath(null);
    }
  }

  async function installManagedRuntime() {
    setInstallingManagedRuntime(true);
    setModelError(null);
    try {
      setManagedRuntime(await invoke<ManagedRuntime>("install_shoko_gguf_runtime_development"));
    } catch (reason) {
      setModelError(message(reason, language === "fr" ? "Le moteur GGUF Shoko n'a pas pu être installé." : "The Shoko GGUF engine could not be installed."));
    } finally {
      setInstallingManagedRuntime(false);
    }
  }

  return (
    <section className="surface models-surface">
      <div className="surface-mark">{language === "fr" ? "ACQUISITION VÉRIFIÉE" : "VERIFIED ACQUISITION"}</div>
      <h2>{language === "fr" ? "Modèles locaux" : "Local models"}</h2>
      <p>{language === "fr" ? "Utilisez les modèles déjà présents, téléchargez-en un nouveau ou inspectez les performances du moteur local." : "Use models already on this machine, download a new one, or inspect local runtime performance."}</p>
      <div className="model-view-tabs" role="group" aria-label={language === "fr" ? "Vue des modèles" : "Model view"}>
        <button type="button" aria-pressed={view === "library"} onClick={() => setView("library")}>{language === "fr" ? "Bibliothèque" : "Library"}</button>
        <button type="button" aria-pressed={view === "download"} onClick={() => setView("download")}>{language === "fr" ? "Télécharger" : "Download"}</button>
        <button type="button" aria-pressed={view === "performance"} onClick={() => setView("performance")}>{language === "fr" ? "Performance" : "Performance"}</button>
      </div>

      {view === "library" && <>
      {lmStudioLibrary?.available && (
        <section className="model-library" aria-labelledby="lm-studio-library-title">
          <div className="model-library-heading">
            <div className="model-section-heading"><HardDrive size={17} /><div><span>{language === "fr" ? "Bibliothèque détectée" : "Detected library"}</span><h3 id="lm-studio-library-title">LM Studio</h3></div></div>
            <div className="model-library-runtime"><p>{language === "fr" ? "Shoko réutilise les fichiers GGUF existants par chemin. Aucun serveur ou moteur LM Studio n'est utilisé." : "Shoko reuses existing GGUF files by path. No LM Studio server or runtime is used."}</p>{managedRuntime?.available ? <span><ShieldCheck size={13} />{language === "fr" ? "Moteur Shoko prêt" : "Shoko engine ready"}</span> : managedRuntime?.reason === "FR-SHOKO-GGUF-RUNTIME-WINDOWS-INTEGRITY-BLOCKED" ? <span><CircleAlert size={13} />{language === "fr" ? "Runtime officiel bloqué par l'intégrité Windows" : "Official runtime blocked by Windows integrity"}</span> : <button className="minor-action" type="button" disabled={installingManagedRuntime} onClick={() => void installManagedRuntime()}><Download size={13} />{installingManagedRuntime ? (language === "fr" ? "Installation" : "Installing") : (language === "fr" ? "Installer le moteur Shoko" : "Install Shoko engine")}</button>}</div>
          </div>
          <div className="model-library-list">
            {lmStudioLibrary.models.map(model => {
              const referenced = referencedPaths.has(model.path);
              return <div className="model-library-row" key={model.path}>
                <div><strong>{model.display_name}</strong><span>{formatBytes(model.size_bytes, language)} · {model.key}</span></div>
                <button className="minor-action" type="button" disabled={!managedRuntime?.available || referenced || referencingPath === model.path} onClick={() => void referenceLibraryModel(model.path)}><Link2 size={13} />{referenced ? (language === "fr" ? "Prêt dans Discussion" : "Ready in Chat") : referencingPath === model.path ? (language === "fr" ? "Connexion" : "Connecting") : (language === "fr" ? "Utiliser dans Shoko" : "Use in Shoko")}</button>
              </div>;
            })}
          </div>
          <p className="model-library-path">{lmStudioLibrary.models_root}</p>
        </section>
      )}

      <div className="model-host-grid">
        <section aria-labelledby="host-capability-title">
          <div className="model-section-heading">
            <HardDrive size={17} />
            <div><span>{language === "fr" ? "Hôte" : "Host"}</span><h3 id="host-capability-title">{report ? `${report.operatingSystem} ${report.architecture}` : (language === "fr" ? "Sonde indisponible" : "Probe unavailable")}</h3></div>
          </div>
          <p>{report ? `${report.logicalCores} ${language === "fr" ? "cœurs logiques" : "logical cores"}` : (error ?? (language === "fr" ? "Vérification en cours" : "Checking"))}</p>
          <button className="minor-action" type="button" onClick={() => void probe()}><RefreshCw size={14} />{language === "fr" ? "Vérifier l'hôte" : "Check host"}</button>
        </section>
        <section aria-labelledby="engine-capability-title">
          <div className="model-section-heading">
            <ShieldCheck size={17} />
            <div><span>{language === "fr" ? "Moteur" : "Engine"}</span><h3 id="engine-capability-title">{engineReport ? `${engineReport.status}, v${engineReport.protocol_version}` : (language === "fr" ? "Diagnostic indisponible" : "Diagnostic unavailable")}</h3></div>
          </div>
          <p>{engineReport ? `${engineReport.host.system} ${engineReport.host.release}, ${engineReport.host.machine}` : (engineError ?? (language === "fr" ? "Vérification en cours" : "Checking"))}</p>
          <button className="minor-action" type="button" onClick={() => void probeEngine()}><RefreshCw size={14} />{language === "fr" ? "Vérifier le moteur" : "Check engine"}</button>
        </section>
      </div>
      </>}

      {view === "download" && <>
      <div className="model-workflow-grid">
        <div className="model-source-column">
          <form className="project-form" onSubmit={search}>
            <label htmlFor="hub-search">{language === "fr" ? "Catalogue public Hugging Face" : "Public Hugging Face catalog"}</label>
            <div className="model-inline-form">
              <input id="hub-search" value={query} onChange={event => setQuery(event.target.value)} placeholder={language === "fr" ? "Chercher un modèle public" : "Search public models"} required />
              <button className="minor-action" type="submit" disabled={searching}><Search size={14} />{searching ? (language === "fr" ? "Recherche" : "Searching") : (language === "fr" ? "Chercher" : "Search")}</button>
            </div>
          </form>
          {models !== null && (
            <div className="model-results" aria-label={language === "fr" ? "Résultats du catalogue" : "Catalog results"}>
              {models.length === 0 && <p>{language === "fr" ? "Aucun modèle public ne correspond." : "No public model matched."}</p>}
              {models.map(model => (
                <div className="model-result" key={model.modelId}>
                  <div><strong>{model.modelId}</strong><span>{language === "fr" ? `${model.downloads ?? 0} téléchargements, ${model.likes ?? 0} favoris` : `${model.downloads ?? 0} downloads, ${model.likes ?? 0} likes`}</span></div>
                  <button className="minor-action" type="button" onClick={() => changeTransferInput(() => setRepositoryId(model.modelId))}>{language === "fr" ? "Utiliser" : "Use"}</button>
                </div>
              ))}
            </div>
          )}

          <form className="project-form model-transfer-form" onSubmit={inspectTransfer}>
            <label htmlFor="transfer-project">{language === "fr" ? "Projet qui conserve la preuve" : "Project that keeps the record"}</label>
            <select id="transfer-project" value={projectId} onChange={event => setProjectId(event.target.value)} required disabled={isTransferActive || activeProjects.length === 0}>
              <option value="">{language === "fr" ? "Choisir un projet local" : "Choose a local project"}</option>
              {activeProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
            {activeProjects.length === 0 && <p className="field-note">{language === "fr" ? "Créez d'abord un projet local dans Projets." : "Create a local project in Projects first."}</p>}
            <div className="model-field-pair">
              <label>Repository ID<input value={repositoryId} onChange={event => changeTransferInput(() => setRepositoryId(event.target.value))} placeholder="org/model" required disabled={isTransferActive} /></label>
              <label>{language === "fr" ? "Révision" : "Revision"}<input value={revision} onChange={event => changeTransferInput(() => setRevision(event.target.value))} placeholder="main" required disabled={isTransferActive} /></label>
            </div>
            <label>{language === "fr" ? "Fichier exact" : "Exact file"}<input value={filename} onChange={event => changeTransferInput(() => setFilename(event.target.value))} placeholder="model-q4_k_m.gguf" required disabled={isTransferActive} /></label>
            <label>{language === "fr" ? "Destination locale" : "Local destination"}<input value={destination} onChange={event => changeTransferInput(() => setDestination(event.target.value))} placeholder={destinationExample} required disabled={isTransferActive} /></label>
            <label>SHA-256 {language === "fr" ? "attendu, facultatif" : "expected, optional"}<input value={sha256} onChange={event => changeTransferInput(() => setSha256(event.target.value))} placeholder="64 hexadecimal characters" pattern="[a-fA-F0-9]{64}" disabled={isTransferActive} /></label>
            <button className="minor-action" type="submit" disabled={planning || isTransferActive || activeProjects.length === 0}><Gauge size={14} />{planning ? (language === "fr" ? "Inspection" : "Inspecting") : (language === "fr" ? "Inspecter le transfert" : "Inspect transfer")}</button>
          </form>
        </div>

        <aside className="transfer-ledger" aria-label={language === "fr" ? "État du transfert" : "Transfer state"}>
          {!plan && !transfer && <div className="transfer-empty"><HardDrive size={22} /><h3>{language === "fr" ? "Aucun préflight" : "No preflight yet"}</h3><p>{language === "fr" ? "Renseignez un fichier exact pour vérifier sa taille et la place requise." : "Enter one exact file to check its size and required space."}</p></div>}
          {plan && !transfer && (
            <div className="transfer-plan">
              <div className="model-section-heading"><FileCheck2 size={17} /><div><span>{language === "fr" ? "Préflight" : "Preflight"}</span><h3>{plan.fits ? (language === "fr" ? "Prêt à transférer" : "Ready to transfer") : (language === "fr" ? "Espace insuffisant" : "Insufficient space")}</h3></div></div>
              <dl>
                <div><dt>{language === "fr" ? "Fichier" : "File"}</dt><dd>{formatBytes(plan.bytes, language)}</dd></div>
                <div><dt>{language === "fr" ? "Requis" : "Required"}</dt><dd>{formatBytes(plan.required_free_bytes, language)}</dd></div>
                <div><dt>{language === "fr" ? "Libre" : "Free"}</dt><dd>{formatBytes(plan.free_bytes, language)}</dd></div>
                <div><dt>Backend</dt><dd>{plan.accelerator}</dd></div>
                <div><dt>{language === "fr" ? "Révision" : "Revision"}</dt><dd>{plan.revision}</dd></div>
                <div><dt>URL</dt><dd title={plan.url}>{plan.url}</dd></div>
              </dl>
              {!plan.fits && <p className="transfer-warning"><CircleAlert size={15} />{language === "fr" ? "Le transfert est bloqué avant toute écriture." : "The transfer is blocked before any write."}</p>}
              <button className="action" type="button" disabled={!plan.fits || !projectId} onClick={() => void startTransfer()}><Download size={15} />{language === "fr" ? "Démarrer le transfert" : "Start transfer"}</button>
            </div>
          )}
          {transfer && (
            <div className="transfer-progress">
              <div className="model-section-heading"><Download size={17} /><div><span>{language === "fr" ? "Tâche" : "Job"} {transfer.id.slice(0, 8)}</span><h3>{stateLabel(transfer.state, language)}</h3></div></div>
              <progress max={100} value={progress?.percent ?? (transfer.state === "succeeded" ? 100 : undefined)} aria-label={language === "fr" ? "Progression du transfert" : "Transfer progress"} />
              <div className="transfer-numbers"><strong>{progress?.percent !== null && progress?.percent !== undefined ? `${progress.percent.toFixed(1)}%` : stateLabel(transfer.state, language)}</strong><span>{formatBytes(progress?.received_bytes ?? transfer.result?.transfer.bytes ?? 0, language)} / {formatBytes(progress?.total_bytes ?? transfer.request.plan.bytes, language)}</span></div>
              <dl>
                <div><dt>{language === "fr" ? "Débit" : "Rate"}</dt><dd>{formatBytes(progress?.bytes_per_second ?? transfer.result?.transfer.bytes_per_second ?? 0, language)}/s</dd></div>
                <div><dt>Backend</dt><dd>{transfer.result?.transfer.method ?? transfer.request.plan.accelerator}</dd></div>
                <div><dt>{language === "fr" ? "Repris" : "Resumed"}</dt><dd>{formatBytes(transfer.result?.transfer.resumed_bytes ?? 0, language)}</dd></div>
                <div><dt>{language === "fr" ? "Destination" : "Destination"}</dt><dd>{transfer.request.destination}</dd></div>
              </dl>
              {isTransferActive && <button className="minor-action danger-action" type="button" onClick={() => void cancelTransfer()} disabled={transfer.state === "cancel_requested"}><Square size={13} />{transfer.state === "cancel_requested" ? (language === "fr" ? "Annulation demandée" : "Cancellation requested") : (language === "fr" ? "Annuler le transfert" : "Cancel transfer")}</button>}
              {(transfer.state === "cancelled" || transfer.state === "failed") && <button className="action" type="button" onClick={() => void retryTransfer()}><RefreshCw size={14} />{language === "fr" ? "Reprendre le transfert" : "Resume transfer"}</button>}
              {terminalStates.has(transfer.state) && <button className="minor-action" type="button" onClick={() => { setTransfer(null); setPlan(null); }}><FileCheck2 size={14} />{language === "fr" ? "Préparer un autre fichier" : "Prepare another file"}</button>}
              {transfer.state === "succeeded" && transfer.result && <div className="transfer-success"><FileCheck2 size={16} /><div><strong>{language === "fr" ? "Fichier vérifié et enregistré" : "File verified and registered"}</strong><span>SHA-256 {transfer.result.transfer.sha256}</span><span>{language === "fr" ? "Capacité" : "Capability"}: {transfer.result.model.capability_state}</span></div></div>}
              {transfer.state === "failed" && transfer.diagnostic && <p className="transfer-warning"><CircleAlert size={15} />{transfer.diagnostic.code}: {transfer.diagnostic.detail ?? (language === "fr" ? "Consultez le journal puis reprenez." : "Inspect the record, then resume.")}</p>}
            </div>
          )}
        </aside>
      </div>

      <div className="engine-report model-runtime-section">
        <div className="surface-mark">OLLAMA</div>
        <h2>{language === "fr" ? "Installer un modèle du runtime local" : "Install a local runtime model"}</h2>
        <form className="project-form" onSubmit={installOllama}>
          <label htmlFor="ollama-project">{language === "fr" ? "Projet" : "Project"}</label>
          <select id="ollama-project" value={projectId} onChange={event => setProjectId(event.target.value)} required disabled={activeProjects.length === 0}>
            <option value="">{language === "fr" ? "Choisir un projet local" : "Choose a local project"}</option>
            {activeProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
          <label>{language === "fr" ? "Identifiant Ollama exact" : "Exact Ollama identifier"}<input value={ollamaModel} onChange={event => setOllamaModel(event.target.value)} placeholder="qwen3" required /></label>
          <button className="minor-action" type="submit" disabled={!projectId}><Download size={14} />{language === "fr" ? "Télécharger avec Ollama" : "Pull with Ollama"}</button>
        </form>
        {ollamaInstall && <div className="transfer-success"><FileCheck2 size={16} /><div><strong>{language === "fr" ? "Journal Ollama" : "Ollama record"}: {ollamaInstall.state}</strong><span>{ollamaInstall.result ? ollamaInstall.result.model : (ollamaInstall.diagnostic?.code ?? ollamaInstall.id)}</span></div></div>}
        <p className="development-note">{language === "fr" ? "Un fichier téléchargé reste non validé pour l'inférence tant qu'un runtime compatible ne l'a pas chargé." : "A downloaded file remains unvalidated for inference until a compatible runtime loads it."}</p>
      </div>
      </>}

      {view === "performance" && (
      <div className="engine-report model-runtime-section">
        <div className="surface-mark">{language === "fr" ? "PROFIL MESURÉ" : "MEASURED PROFILE"}</div>
        <h2>{language === "fr" ? "Planifier et préchauffer Ollama" : "Plan and warm up Ollama"}</h2>
        <p>{language === "fr" ? "Le plan vérifie les modèles installés, la mémoire et les limites demandées avant tout chargement." : "The plan checks installed models, memory, and requested limits before loading anything."}</p>
        <div className="inference-profile-grid">
          <form className="project-form inference-profile-form" onSubmit={inspectInference}>
            <label>{language === "fr" ? "Modèles exacts, séparés par une virgule" : "Exact models, comma separated"}<input value={profileModels} onChange={event => setProfileModels(event.target.value)} placeholder="qwen3" required /></label>
            <div className="inference-field-grid">
              <label>{language === "fr" ? "Contexte, auto si vide" : "Context, auto when empty"}<input type="number" min="512" max="262144" value={contextLength} onChange={event => setContextLength(event.target.value)} placeholder="4096" /></label>
              <label>{language === "fr" ? "Threads CPU, auto si vide" : "CPU threads, auto when empty"}<input type="number" min="1" value={cpuThreads} onChange={event => setCpuThreads(event.target.value)} placeholder={report?.logicalCores.toString() ?? "8"} /></label>
              <label>{language === "fr" ? "Lot, auto si vide" : "Batch, auto when empty"}<input type="number" min="1" max="2048" value={batchSize} onChange={event => setBatchSize(event.target.value)} placeholder="512" /></label>
              <label>{language === "fr" ? "Couches GPU, auto si vide" : "GPU layers, auto when empty"}<input type="number" min="0" value={gpuLayers} onChange={event => setGpuLayers(event.target.value)} placeholder="auto" /></label>
              <label>{language === "fr" ? "Conservation en mémoire" : "Keep in memory"}<input value={keepAlive} onChange={event => setKeepAlive(event.target.value)} placeholder="15m" required /></label>
              <label>{language === "fr" ? "Requêtes parallèles" : "Parallel requests"}<input type="number" min="1" max="16" value={concurrency} onChange={event => setConcurrency(event.target.value)} required /></label>
            </div>
            <button className="minor-action" type="submit" disabled={inspectingInference}><Gauge size={14} />{inspectingInference ? (language === "fr" ? "Calcul" : "Calculating") : (language === "fr" ? "Calculer le profil" : "Calculate profile")}</button>
          </form>

          <section className="inference-ledger" aria-label={language === "fr" ? "Compatibilité d'inférence" : "Inference compatibility"}>
            {!inferencePlan && <div className="transfer-empty"><Cpu size={22} /><h3>{language === "fr" ? "Aucun profil calculé" : "No calculated profile"}</h3><p>{language === "fr" ? "Le runtime et la mémoire seront sondés à la demande." : "Runtime and memory will be probed on demand."}</p></div>}
            {inferencePlan && <>
              <div className="model-section-heading"><Cpu size={17} /><div><span>{inferencePlan.memory_source === "gpu" ? "GPU" : "CPU"}</span><h3>{inferencePlan.supported ? (language === "fr" ? "Chargement compatible" : "Load supported") : (language === "fr" ? "Chargement refusé" : "Load refused")}</h3></div></div>
              <dl>
                <div><dt>{language === "fr" ? "Modèles" : "Models"}</dt><dd>{inferencePlan.models.join(", ")}</dd></div>
                <div><dt>{language === "fr" ? "Mémoire estimée" : "Estimated memory"}</dt><dd>{formatBytes(inferencePlan.estimated_working_set_bytes, language)}</dd></div>
                <div><dt>{language === "fr" ? "Budget sûr" : "Safe budget"}</dt><dd>{formatBytes(inferencePlan.memory_budget_bytes, language)}</dd></div>
                <div><dt>{language === "fr" ? "Contexte" : "Context"}</dt><dd>{inferencePlan.options.num_ctx.toLocaleString()}</dd></div>
                <div><dt>Batch</dt><dd>{inferencePlan.options.num_batch.toLocaleString()}</dd></div>
                <div><dt>Threads</dt><dd>{inferencePlan.options.num_thread}</dd></div>
                <div><dt>{language === "fr" ? "Parallélisme" : "Concurrency"}</dt><dd>{inferencePlan.concurrency}</dd></div>
                {inferencePlan.automatic_cpu_fallback && <div><dt>Fallback</dt><dd>CPU</dd></div>}
              </dl>
              {!inferencePlan.supported && <p className="transfer-warning"><CircleAlert size={15} />{inferencePlan.reasons.join(", ")}</p>}
              {inferencePlan.supported && inferencePlan.models.length === 1 && <button className="action" type="button" onClick={() => void warmupModel()} disabled={warmingModel}><Thermometer size={14} />{warmingModel ? (language === "fr" ? "Préchauffage" : "Warming up") : (language === "fr" ? "Préchauffer et vérifier" : "Warm up and verify")}</button>}
              {inferencePlan.supported && inferencePlan.models.length > 1 && <p className="field-note">{language === "fr" ? "Le plan multi-modèle est compatible. Préchargez chaque modèle séparément pour conserver une preuve exacte." : "The multi-model plan is compatible. Warm each model separately to keep exact evidence."}</p>}
              {warmup && <div className="transfer-success"><FileCheck2 size={16} /><div><strong>{language === "fr" ? "Modèle chargé et vérifié" : "Model loaded and verified"}</strong><span>{language === "fr" ? "Chargement" : "Load"}: {formatNanoseconds(warmup.metrics.load_duration, language)}</span><span>Total: {formatNanoseconds(warmup.metrics.total_duration, language)}</span><span>VRAM: {formatBytes(warmup.loaded.size_vram ?? null, language)}, ctx {warmup.loaded.context_length ?? inferencePlan.options.num_ctx}</span></div></div>}
            </>}
          </section>
        </div>
      </div>
      )}

      {modelError && <div className="model-error" role="alert"><CircleAlert size={17} /><div><strong>{language === "fr" ? "Action interrompue" : "Action stopped"}</strong><p>{modelError}</p></div></div>}
    </section>
  );
}

function stateLabel(state: ModelTransfer["state"], language: Language): string {
  const labels: Record<ModelTransfer["state"], [string, string]> = {
    queued: ["Queued", "En attente"],
    running: ["Transferring", "Transfert en cours"],
    cancel_requested: ["Stopping", "Arrêt en cours"],
    cancelled: ["Cancelled", "Annulé"],
    succeeded: ["Verified", "Vérifié"],
    failed: ["Failed", "Échec"],
  };
  return labels[state][language === "fr" ? 1 : 0];
}

function message(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : typeof reason === "string" ? reason : fallback;
}
