import { invoke } from "@tauri-apps/api/core";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { CircleAlert, FileCheck2, GitFork, Play, Plus, RefreshCw, RotateCcw, ShieldCheck, Square, Timer, Trash2, Workflow } from "lucide-react";
import type { Language } from "./i18n";

type ProjectRecord = { id: string; name: string; archived_at: string | null };
type CapabilityItem = { id: string; external_effects?: boolean };
type PipelineCapabilities = { step_types: CapabilityItem[]; skills: CapabilityItem[]; connectors: CapabilityItem[]; schedules: CapabilityItem[] };
type PipelineStep = { key: string; kind: "model" | "skill" | "connector"; config: Record<string, unknown>; depends_on: string[]; max_retries: number; external_effects: boolean };
type Pipeline = { id: string; project_id: string; name: string; schedule: { kind: "manual" | "interval"; interval_seconds?: number }; enabled: boolean; next_due_at: string | null; external_effects: boolean; steps: PipelineStep[] };
type StepRun = { id: string; step_key: string; attempt: number; state: string; output: Record<string, unknown> | null; diagnostic: { code: string; detail?: string } | null };
type PipelineRun = { id: string; automation_id: string; mode: string; state: string; external_effects: boolean; external_approved: boolean; trigger_kind: string; parent_run_id: string | null; diagnostic: { code: string; detail?: string; step?: string } | null; created_at: string; steps: StepRun[] };
type Catalog = { capabilities: PipelineCapabilities; pipelines: Pipeline[]; runs: PipelineRun[] };
type EditorStep = { key: string; kind: PipelineStep["kind"]; target: string; prompt: string; code: string; query: string; dependencies: string; retries: string };

const terminalStates = new Set(["simulated", "succeeded", "failed", "cancelled"]);

function newStep(index: number): EditorStep {
  return { key: `step${index + 1}`, kind: "skill", target: "evidence-review", prompt: "", code: "", query: "", dependencies: "", retries: "0" };
}

export function toPipelineSteps(steps: EditorStep[]): Array<Omit<PipelineStep, "external_effects">> {
  return steps.map(step => {
    const config: Record<string, unknown> = step.kind === "model"
      ? { model: step.target.trim(), prompt: step.prompt.trim() }
      : step.kind === "skill"
        ? { skill_id: step.target, ...(step.target === "reproducible-kernel" ? { code: step.code } : {}) }
        : { connector_id: step.target, ...(step.target === "huggingface-model-catalog" ? { query: step.query, limit: 10 } : {}) };
    return {
      key: step.key.trim(),
      kind: step.kind,
      config,
      depends_on: step.dependencies.split(",").map(value => value.trim()).filter(Boolean),
      max_retries: Number.parseInt(step.retries, 10) || 0,
    };
  });
}

export function AutomationsSurface({ projects, language }: { projects: ProjectRecord[] | null; language: Language }) {
  const activeProjects = projects?.filter(project => project.archived_at === null) ?? [];
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [projectId, setProjectId] = useState("");
  const [name, setName] = useState("");
  const [scheduleKind, setScheduleKind] = useState<"manual" | "interval">("manual");
  const [intervalSeconds, setIntervalSeconds] = useState("3600");
  const [steps, setSteps] = useState<EditorStep[]>([newStep(0)]);
  const [selectedPipelineId, setSelectedPipelineId] = useState<string | null>(null);
  const [currentRun, setCurrentRun] = useState<PipelineRun | null>(null);
  const [externalApproved, setExternalApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedPipeline = catalog?.pipelines.find(pipeline => pipeline.id === selectedPipelineId) ?? catalog?.pipelines[0] ?? null;
  const pipelineRuns = useMemo(() => catalog?.runs.filter(run => run.automation_id === selectedPipeline?.id) ?? [], [catalog?.runs, selectedPipeline?.id]);

  async function refresh() {
    setError(null);
    try {
      const next = await invoke<Catalog>("automations_development", { projectId: projectId || null });
      setCatalog(next);
      setSelectedPipelineId(previous => previous && next.pipelines.some(item => item.id === previous) ? previous : (next.pipelines[0]?.id ?? null));
    } catch (reason) {
      setError(message(reason, language === "fr" ? "Le registre des automatisations est indisponible." : "Automation ledger is unavailable."));
    }
  }

  useEffect(() => {
    if (!projectId && activeProjects[0]) setProjectId(activeProjects[0].id);
  }, [activeProjects, projectId]);

  useEffect(() => {
    void refresh();
  }, [projectId]);

  useEffect(() => {
    if (!("__TAURI_INTERNALS__" in window)) return;
    const timer = window.setInterval(() => {
      void invoke("run_due_automations_development").then(() => refresh()).catch(() => undefined);
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [projectId]);

  useEffect(() => {
    if (!currentRun || terminalStates.has(currentRun.state)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await invoke<PipelineRun>("automation_status_development", { automationRunId: currentRun.id });
        setCurrentRun(next);
        if (terminalStates.has(next.state)) await refresh();
      } catch (reason) {
        setError(message(reason, language === "fr" ? "Le statut du pipeline est indisponible." : "Pipeline status is unavailable."));
      }
    }, 750);
    return () => window.clearInterval(timer);
  }, [currentRun?.id, currentRun?.state]);

  function updateStep(index: number, update: Partial<EditorStep>) {
    setSteps(current => current.map((step, position) => position === index ? { ...step, ...update } : step));
  }

  function changeStepKind(index: number, kind: EditorStep["kind"]) {
    const target = kind === "model" ? "" : kind === "skill" ? (catalog?.capabilities.skills[0]?.id ?? "") : (catalog?.capabilities.connectors[0]?.id ?? "");
    updateStep(index, { kind, target });
  }

  async function createPipeline(event: FormEvent) {
    event.preventDefault();
    if (!projectId) return;
    setBusy(true);
    setError(null);
    try {
      const schedule = scheduleKind === "manual" ? { kind: "manual" } : { kind: "interval", interval_seconds: Number.parseInt(intervalSeconds, 10) };
      const created = await invoke<Pipeline>("create_automation_development", { projectId, name, steps: toPipelineSteps(steps), schedule });
      setName("");
      setSteps([newStep(0)]);
      setCurrentRun(null);
      await refresh();
      setSelectedPipelineId(created.id);
    } catch (reason) {
      setError(message(reason, language === "fr" ? "Le pipeline n'a pas été créé." : "Pipeline creation failed."));
    } finally {
      setBusy(false);
    }
  }

  async function startPipeline(execute: boolean) {
    if (!selectedPipeline) return;
    setBusy(true);
    setError(null);
    try {
      const run = await invoke<PipelineRun>("start_automation_development", { automationId: selectedPipeline.id, execute, externalApproved: execute && externalApproved });
      setCurrentRun(run);
      await refresh();
    } catch (reason) {
      setError(message(reason, language === "fr" ? "Le pipeline n'a pas démarré." : "Pipeline did not start."));
    } finally {
      setBusy(false);
    }
  }

  async function cancelRun() {
    if (!currentRun) return;
    setCurrentRun(await invoke<PipelineRun>("cancel_automation_development", { automationRunId: currentRun.id }));
  }

  async function retryRun(runId: string) {
    setCurrentRun(await invoke<PipelineRun>("retry_automation_development", { automationRunId: runId, externalApproved: selectedPipeline?.external_effects ? externalApproved : false }));
    await refresh();
  }

  return (
    <section className="surface automations-surface">
      <div className="surface-mark">{language === "fr" ? "DAG LOCAL DURABLE" : "DURABLE LOCAL DAG"}</div>
      <h2>{language === "fr" ? "Pipelines et automatisations" : "Pipelines and automations"}</h2>
      <p>{language === "fr" ? "Composez des étapes exécutables, vérifiez le graphe à sec, puis conservez chaque tentative et sortie." : "Compose executable steps, validate the graph with a dry run, then retain every attempt and output."}</p>

      <div className="automation-layout">
        <form className="automation-editor" onSubmit={createPipeline}>
          <div className="automation-heading"><Workflow size={17} /><div><span>{language === "fr" ? "ÉDITEUR" : "EDITOR"}</span><h3>{language === "fr" ? "Nouveau pipeline" : "New pipeline"}</h3></div></div>
          <label>{language === "fr" ? "Projet" : "Project"}<select value={projectId} onChange={event => setProjectId(event.target.value)} required disabled={activeProjects.length === 0}><option value="">{language === "fr" ? "Choisir un projet" : "Choose a project"}</option>{activeProjects.map(project => <option value={project.id} key={project.id}>{project.name}</option>)}</select></label>
          <label>{language === "fr" ? "Nom" : "Name"}<input value={name} onChange={event => setName(event.target.value)} placeholder={language === "fr" ? "Revue scientifique" : "Scientific review"} required /></label>
          <div className="automation-schedule">
            <label>{language === "fr" ? "Cadence" : "Schedule"}<select value={scheduleKind} onChange={event => setScheduleKind(event.target.value as "manual" | "interval")}><option value="manual">{language === "fr" ? "Manuel" : "Manual"}</option><option value="interval">Interval</option></select></label>
            {scheduleKind === "interval" && <label>{language === "fr" ? "Secondes" : "Seconds"}<input type="number" min="60" max="31536000" value={intervalSeconds} onChange={event => setIntervalSeconds(event.target.value)} required /></label>}
          </div>

          <div className="automation-steps">
            {steps.map((step, index) => <article className="automation-step" key={`${index}-${step.key}`}>
              <div className="automation-step-head"><span>{index + 1}</span><strong>{step.key || (language === "fr" ? "Étape sans nom" : "Unnamed step")}</strong>{steps.length > 1 && <button className="icon-button" type="button" onClick={() => setSteps(current => current.filter((_, position) => position !== index))} aria-label={language === "fr" ? "Supprimer l'étape" : "Remove step"}><Trash2 size={14} /></button>}</div>
              <div className="automation-field-grid">
                <label>Key<input value={step.key} onChange={event => updateStep(index, { key: event.target.value })} pattern="[A-Za-z][A-Za-z0-9_-]{0,63}" required /></label>
                <label>Type<select value={step.kind} onChange={event => changeStepKind(index, event.target.value as EditorStep["kind"])}>{catalog?.capabilities.step_types.map(item => <option value={item.id} key={item.id}>{item.id}</option>)}</select></label>
              </div>
              {step.kind === "model" && <><label>{language === "fr" ? "Modèle exact" : "Exact model"}<input value={step.target} onChange={event => updateStep(index, { target: event.target.value })} placeholder="qwen3" required /></label><label>Prompt<textarea value={step.prompt} onChange={event => updateStep(index, { prompt: event.target.value })} required /></label></>}
              {step.kind === "skill" && <><label>Skill<select value={step.target} onChange={event => updateStep(index, { target: event.target.value })}>{catalog?.capabilities.skills.map(item => <option value={item.id} key={item.id}>{item.id}</option>)}</select></label>{step.target === "reproducible-kernel" && <label>Python<textarea value={step.code} onChange={event => updateStep(index, { code: event.target.value })} placeholder="print('ready')" /></label>}</>}
              {step.kind === "connector" && <><label>{language === "fr" ? "Connecteur vérifié" : "Verified connector"}<select value={step.target} onChange={event => updateStep(index, { target: event.target.value })}>{catalog?.capabilities.connectors.map(item => <option value={item.id} key={item.id}>{item.id}{item.external_effects ? " · approval" : ""}</option>)}</select></label>{step.target === "huggingface-model-catalog" && <label>{language === "fr" ? "Recherche" : "Query"}<input value={step.query} onChange={event => updateStep(index, { query: event.target.value })} required /></label>}</>}
              <div className="automation-field-grid"><label>{language === "fr" ? "Dépendances, clés séparées par virgule" : "Dependencies, comma separated keys"}<input value={step.dependencies} onChange={event => updateStep(index, { dependencies: event.target.value })} /></label><label>{language === "fr" ? "Reprises" : "Retries"}<input type="number" min="0" max="5" value={step.retries} onChange={event => updateStep(index, { retries: event.target.value })} /></label></div>
            </article>)}
          </div>
          <button className="minor-action" type="button" onClick={() => setSteps(current => [...current, newStep(current.length)])}><Plus size={14} />{language === "fr" ? "Ajouter une étape" : "Add step"}</button>
          <button className="action" type="submit" disabled={busy || !catalog || activeProjects.length === 0}><FileCheck2 size={14} />{language === "fr" ? "Enregistrer le pipeline" : "Save pipeline"}</button>
        </form>

        <div className="automation-ledger">
          <div className="automation-heading"><GitFork size={17} /><div><span>{language === "fr" ? "REGISTRE" : "LEDGER"}</span><h3>{catalog ? `${catalog.pipelines.length} pipeline${catalog.pipelines.length === 1 ? "" : "s"}` : (language === "fr" ? "Indisponible" : "Unavailable")}</h3></div><button className="icon-button" type="button" onClick={() => void refresh()} aria-label={language === "fr" ? "Actualiser" : "Refresh"}><RefreshCw size={14} /></button></div>
          {catalog?.pipelines.length === 0 && <div className="transfer-empty"><Workflow size={22} /><h3>{language === "fr" ? "Aucun pipeline" : "No pipeline"}</h3><p>{language === "fr" ? "Ajoutez une première étape réellement exécutable." : "Add a first step that can actually execute."}</p></div>}
          {catalog && catalog.pipelines.length > 0 && <div className="pipeline-list">{catalog.pipelines.map(pipeline => <button type="button" key={pipeline.id} aria-pressed={selectedPipeline?.id === pipeline.id} onClick={() => { setSelectedPipelineId(pipeline.id); setCurrentRun(null); setExternalApproved(false); }}><span><strong>{pipeline.name}</strong><small>{pipeline.steps.length} steps · {pipeline.schedule.kind}</small></span>{pipeline.external_effects ? <ShieldCheck size={14} /> : <GitFork size={14} />}</button>)}</div>}
          {selectedPipeline && <div className="pipeline-detail">
            <div className="pipeline-meta"><span><Timer size={13} />{selectedPipeline.next_due_at ? new Date(selectedPipeline.next_due_at).toLocaleString() : (language === "fr" ? "Déclenchement manuel" : "Manual trigger")}</span><span>{selectedPipeline.external_effects ? (language === "fr" ? "Approbation requise" : "Approval required") : (language === "fr" ? "Effets locaux" : "Local effects")}</span></div>
            <ol>{selectedPipeline.steps.map(step => <li key={step.key}><span>{step.key}</span><code>{step.kind}</code><small>{step.depends_on.length ? `after ${step.depends_on.join(", ")}` : "root"}</small></li>)}</ol>
            {selectedPipeline.external_effects && <label className="approval-check"><input type="checkbox" checked={externalApproved} onChange={event => setExternalApproved(event.target.checked)} />{language === "fr" ? "J'approuve explicitement l'accès réseau de cette exécution" : "I explicitly approve network access for this run"}</label>}
            <div className="pipeline-actions"><button className="minor-action" type="button" onClick={() => void startPipeline(false)} disabled={busy}><FileCheck2 size={14} />Dry run</button><button className="action" type="button" onClick={() => void startPipeline(true)} disabled={busy || (selectedPipeline.external_effects && !externalApproved)}><Play size={14} />{language === "fr" ? "Exécuter" : "Execute"}</button></div>
          </div>}
          {pipelineRuns.length > 0 && <div className="pipeline-history"><span>{language === "fr" ? "HISTORIQUE" : "HISTORY"}</span>{pipelineRuns.slice(0, 5).map(run => <button type="button" key={run.id} aria-pressed={(currentRun?.id ?? pipelineRuns[0]?.id) === run.id} onClick={() => setCurrentRun(run)}><strong>{run.state}</strong><small>{new Date(run.created_at).toLocaleString()}</small></button>)}</div>}
          {(currentRun && currentRun.automation_id === selectedPipeline?.id ? currentRun : pipelineRuns[0]) && <RunDetail run={currentRun && currentRun.automation_id === selectedPipeline?.id ? currentRun : pipelineRuns[0]} language={language} onCancel={cancelRun} onRetry={retryRun} retryApprovalRequired={Boolean(selectedPipeline?.external_effects && !externalApproved)} />}
        </div>
      </div>
      {error && <div className="model-error" role="alert"><CircleAlert size={17} /><div><strong>{language === "fr" ? "Action interrompue" : "Action stopped"}</strong><p>{error}</p></div></div>}
    </section>
  );
}

function RunDetail({ run, language, onCancel, onRetry, retryApprovalRequired }: { run: PipelineRun; language: Language; onCancel: () => Promise<void>; onRetry: (runId: string) => Promise<void>; retryApprovalRequired: boolean }) {
  return <section className="pipeline-run"><div className="automation-heading"><Play size={16} /><div><span>{run.trigger_kind}</span><h3>{run.mode}: {run.state}</h3></div></div>{run.steps.length > 0 && <ul>{run.steps.map(step => <li key={step.id}><span>{step.step_key}, {language === "fr" ? "tentative" : "attempt"} {step.attempt}</span><strong>{step.state}</strong>{step.diagnostic && <small>{step.diagnostic.code}</small>}{step.output && <details><summary>{language === "fr" ? "Sortie conservée" : "Retained output"}</summary><pre>{JSON.stringify(step.output, null, 2)}</pre></details>}</li>)}</ul>}{["queued", "running", "cancel_requested"].includes(run.state) && <button className="minor-action danger-action" type="button" onClick={() => void onCancel()} disabled={run.state === "cancel_requested"}><Square size={13} />{language === "fr" ? "Annuler" : "Cancel"}</button>}{["failed", "cancelled"].includes(run.state) && <button className="minor-action" type="button" onClick={() => void onRetry(run.id)} disabled={retryApprovalRequired}><RotateCcw size={13} />{language === "fr" ? "Reprendre" : "Retry"}</button>}{run.diagnostic && <p className="transfer-warning"><CircleAlert size={14} />{run.diagnostic.code}: {run.diagnostic.step ?? run.diagnostic.detail}</p>}</section>;
}

function message(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : typeof reason === "string" ? reason : fallback;
}
