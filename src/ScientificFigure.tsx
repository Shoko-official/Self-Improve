import { invoke } from "@tauri-apps/api/core";
import { useEffect, useId, useMemo, useState, type FormEvent, type KeyboardEvent } from "react";
import { Braces, ChartScatter, CircleAlert, Dna, Eye, GitBranch, Grid3x3, MousePointer2, Save, SlidersHorizontal } from "lucide-react";
import type { Language } from "./i18n";

type ScatterPoint = { id: string; x: number; y: number; category: string; label: string };
type MatrixCell = { row: number; column: number; value: number; size: number };
type SequenceFeature = { id: string; start: number; end: number; label: string; category: string };
type TreeNode = { id: string; parent_id: string | null; label: string; category: string };

export type ScientificFigureData = {
  version: 1;
  kind: "scatter" | "matrix" | "sequence" | "tree" | "genome";
  title: string;
  subtitle: string;
  x_label?: string;
  y_label?: string;
  points?: ScatterPoint[];
  rows?: string[];
  columns?: string[];
  cells?: MatrixCell[];
  length?: number;
  features?: SequenceFeature[];
  nodes?: TreeNode[];
};

type FigurePreview = {
  renderer_id: string;
  renderer_version: string;
  source_sha256: string;
  figure: ScientificFigureData;
  warnings: string[];
  selector_schema: Record<string, unknown>;
  execution: "disabled";
};

type FigureSelector = { kind: "point"; id: string } | { kind: "cell"; row: number; column: number } | { kind: "feature"; id: string } | { kind: "node"; id: string };
type ProjectOption = { id: string; name: string; archived_at: string | null };

const palette = ["#5f88ad", "#b87356", "#78935f", "#9277a2", "#b3934f", "#57908a", "#ad6575"];

function buildScatterTemplatePoints(): ScatterPoint[] {
  const clusters = [
    { category: "Neural", x: -2.7, y: -1.1, scaleX: 1.25, scaleY: .8, count: 80 },
    { category: "Immune", x: 2.55, y: 1.15, scaleX: .75, scaleY: .62, count: 50 },
    { category: "Stromal", x: .2, y: 1.75, scaleX: 1.05, scaleY: .55, count: 60 },
    { category: "Epithelial", x: .65, y: -.55, scaleX: .82, scaleY: .68, count: 50 },
    { category: "Cycling", x: 2.05, y: -1.65, scaleX: .72, scaleY: .45, count: 40 },
    { category: "Vascular", x: -1.25, y: 1.55, scaleX: .5, scaleY: .43, count: 38 },
  ];
  let pointIndex = 0;
  return clusters.flatMap((cluster, clusterIndex) => Array.from({ length: cluster.count }, (_, index) => {
    const angle = index * 2.399963 + clusterIndex * .61;
    const radius = Math.sqrt((index + .65) / cluster.count);
    const ripple = Math.sin((index + 1) * (clusterIndex + 2)) * .11;
    pointIndex += 1;
    return {
      id: `cell-${String(pointIndex).padStart(3, "0")}`,
      x: Number((cluster.x + Math.cos(angle) * cluster.scaleX * radius + ripple).toFixed(3)),
      y: Number((cluster.y + Math.sin(angle) * cluster.scaleY * radius - ripple * .45).toFixed(3)),
      category: cluster.category,
      label: `Cell ${String(pointIndex).padStart(3, "0")}`,
    };
  }));
}

function buildMatrixTemplateCells(rowCount: number, columnCount: number): MatrixCell[] {
  return Array.from({ length: rowCount * columnCount }, (_, index) => {
    const row = Math.floor(index / columnCount);
    const column = index % columnCount;
    const distance = Math.abs(row - column * rowCount / columnCount);
    const value = Math.max(.08, .95 - distance * .16 + ((row * 7 + column * 3) % 5) * .025);
    const size = Math.max(.12, .9 - distance * .13 + ((row + column * 2) % 4) * .035);
    return { row, column, value: Number(value.toFixed(3)), size: Number(size.toFixed(3)) };
  });
}

export const figureTemplates: Record<ScientificFigureData["kind"], string> = {
  scatter: JSON.stringify({
    version: 1,
    kind: "scatter",
    title: "Cross-species cell atlas",
    subtitle: "318 cells, 6 inferred families, local draft",
    x_label: "UMAP 1",
    y_label: "UMAP 2",
    points: buildScatterTemplatePoints(),
  }, null, 2),
  matrix: JSON.stringify({
    version: 1,
    kind: "matrix",
    title: "Cell-type markers",
    subtitle: "Size and tone encode independent measurements",
    rows: ["T cell", "B cell", "NK cell", "Monocyte", "Macrophage", "Dendritic", "Fibroblast", "Endothelial"],
    columns: ["CD3E", "MS4A1", "NKG7", "LYZ", "CD14", "C1QC", "FCGR3A", "COL1A1", "DCN", "PECAM1", "VWF", "KDR"],
    cells: buildMatrixTemplateCells(8, 12),
  }, null, 2),
  sequence: JSON.stringify({
    version: 1,
    kind: "sequence",
    title: "Protein domain architecture",
    subtitle: "Local draft with exact feature coordinates",
    length: 980,
    features: [
      { id: "signal", start: 8, end: 42, label: "Signal peptide", category: "Signal" },
      { id: "domain-a", start: 76, end: 246, label: "Catalytic A", category: "Domain" },
      { id: "motif-a", start: 188, end: 216, label: "Active site", category: "Motif" },
      { id: "linker-a", start: 270, end: 338, label: "Linker", category: "Linker" },
      { id: "domain-b", start: 360, end: 612, label: "Regulatory", category: "Domain" },
      { id: "motif-b", start: 528, end: 552, label: "Binding motif", category: "Motif" },
      { id: "domain-c", start: 660, end: 876, label: "Interaction", category: "Domain" },
      { id: "tail", start: 900, end: 968, label: "Tail", category: "Disordered" },
    ],
  }, null, 2),
  genome: JSON.stringify({ version: 1, kind: "genome", title: "Local genome locus", subtitle: "Feature coordinates are local draft data", length: 1200, features: [{ id: "gene-a", start: 120, end: 840, label: "GENE A", category: "Gene" }, { id: "exon-a", start: 260, end: 420, label: "Exon 1", category: "Exon" }] }, null, 2),
  tree: JSON.stringify({ version: 1, kind: "tree", title: "Local phylogeny", subtitle: "Topology is a local draft", nodes: [{ id: "root", label: "Ancestor" }, { id: "alpha", parent_id: "root", label: "Alpha" }, { id: "beta", parent_id: "root", label: "Beta" }] }, null, 2),
};

function localFigurePreview(source: string): FigurePreview {
  const figure = JSON.parse(source) as ScientificFigureData;
  if (figure.version !== 1 || !["scatter", "matrix", "sequence", "tree", "genome"].includes(figure.kind)) {
    throw new Error("FR-RENDERER-FIGURE: unsupported local figure contract");
  }
  return {
    renderer_id: "local-draft",
    renderer_version: "1",
    source_sha256: "pending-engine-validation",
    figure,
    warnings: [],
    selector_schema: {},
    execution: "disabled",
  };
}

function useCategoryColors(categories: string[]) {
  return useMemo(() => new Map([...new Set(categories)].sort().map((category, index) => [category, palette[index % palette.length]])), [categories.join("\u0000")]);
}

function selectorKey(selector: FigureSelector) {
  return selector.kind === "cell" ? `cell:${selector.row}:${selector.column}` : `${selector.kind}:${selector.id}`;
}

function activate(event: KeyboardEvent<SVGElement>, callback: () => void) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    callback();
  }
}

export function ScientificFigureView({ figure, selected, onSelect }: { figure: ScientificFigureData; selected?: FigureSelector | null; onSelect?: (selector: FigureSelector) => void }) {
  const titleId = useId();
  const selectedKey = selected ? selectorKey(selected) : "";
  const content = figure.kind === "scatter"
    ? <ScatterFigure figure={figure} selectedKey={selectedKey} onSelect={onSelect} />
    : figure.kind === "matrix"
      ? <MatrixFigure figure={figure} selectedKey={selectedKey} onSelect={onSelect} />
      : figure.kind === "tree" ? <TreeFigure figure={figure} selectedKey={selectedKey} onSelect={onSelect} /> : <SequenceFigure figure={figure} selectedKey={selectedKey} onSelect={onSelect} />;
  const FigureIcon = figure.kind === "scatter" ? ChartScatter : figure.kind === "matrix" ? Grid3x3 : Dna;
  return (
    <figure className="scientific-figure">
      <figcaption>
        <span><FigureIcon size={17} /></span>
        <div><h3 id={titleId}>{figure.title}</h3>{figure.subtitle && <p>{figure.subtitle}</p>}</div>
        <code>figure.{figure.kind}/v1</code>
      </figcaption>
      <div className="scientific-canvas">
        <svg viewBox="0 0 760 620" role="img" aria-labelledby={titleId}>{content}</svg>
      </div>
    </figure>
  );
}

function ScatterFigure({ figure, selectedKey, onSelect }: { figure: ScientificFigureData; selectedKey: string; onSelect?: (selector: FigureSelector) => void }) {
  const points = figure.points ?? [];
  const colors = useCategoryColors(points.map(point => point.category));
  const xs = points.map(point => point.x);
  const ys = points.map(point => point.y);
  const xMin = Math.min(...xs), xMax = Math.max(...xs), yMin = Math.min(...ys), yMax = Math.max(...ys);
  const xRange = xMax - xMin || 1, yRange = yMax - yMin || 1;
  const x = (value: number) => 72 + ((value - xMin) / xRange) * 630;
  const y = (value: number) => 520 - ((value - yMin) / yRange) * 448;
  return <>
    {[0, 1, 2, 3, 4].map(index => <g key={index}><line className="figure-grid" x1={72} x2={702} y1={72 + index * 112} y2={72 + index * 112} /><line className="figure-grid" y1={72} y2={520} x1={72 + index * 157.5} x2={72 + index * 157.5} /></g>)}
    <line className="figure-axis" x1="72" x2="702" y1="520" y2="520" /><line className="figure-axis" x1="72" x2="72" y1="72" y2="520" />
    <text className="figure-axis-label" x="387" y="594" textAnchor="middle">{figure.x_label}</text>
    <text className="figure-axis-label" x="20" y="296" textAnchor="middle" transform="rotate(-90 20 296)">{figure.y_label}</text>
    {points.map(point => {
      const selector: FigureSelector = { kind: "point", id: point.id };
      const selected = selectedKey === selectorKey(selector);
      return <circle key={point.id} className={selected ? "figure-mark selected" : "figure-mark"} cx={x(point.x)} cy={y(point.y)} r={selected ? 6 : 3} fill={colors.get(point.category)} tabIndex={0} role="button" aria-label={`${point.label}, ${point.category}, x ${point.x}, y ${point.y}`} data-selector={JSON.stringify(selector)} onClick={() => onSelect?.(selector)} onKeyDown={event => activate(event, () => onSelect?.(selector))}><title>{point.label}</title></circle>;
    })}
    {[...colors].map(([category, color], index) => <g key={category} transform={`translate(${86 + index * 124} 558)`}><circle r="4" fill={color} /><text className="figure-legend" x="10" y="4">{category}</text></g>)}
  </>;
}

function MatrixFigure({ figure, selectedKey, onSelect }: { figure: ScientificFigureData; selectedKey: string; onSelect?: (selector: FigureSelector) => void }) {
  const rows = figure.rows ?? [], columns = figure.columns ?? [], cells = figure.cells ?? [];
  const values = cells.map(cell => cell.value), sizes = cells.map(cell => cell.size);
  const valueMin = Math.min(...values), valueRange = Math.max(...values) - valueMin || 1, sizeMax = Math.max(...sizes) || 1;
  const width = 580 / columns.length, height = 400 / rows.length;
  return <>
    {rows.map((row, index) => <text key={row} className="figure-tick" x="145" y={90 + index * height + height / 2 + 4} textAnchor="end">{row}</text>)}
    {columns.map((column, index) => <text key={column} className="figure-tick" x={160 + index * width + width / 2} y="65" textAnchor="middle">{column}</text>)}
    {rows.flatMap((_, row) => columns.map((__, column) => <rect key={`${row}:${column}`} className="figure-matrix-cell" x={160 + column * width} y={90 + row * height} width={width} height={height} />))}
    {cells.map(cell => {
      const selector: FigureSelector = { kind: "cell", row: cell.row, column: cell.column };
      const selected = selectedKey === selectorKey(selector);
      const radius = 4 + Math.sqrt(cell.size / sizeMax) * Math.min(18, width * 0.28, height * 0.28);
      return <circle key={`${cell.row}:${cell.column}`} className={selected ? "figure-matrix-mark selected" : "figure-matrix-mark"} cx={160 + cell.column * width + width / 2} cy={90 + cell.row * height + height / 2} r={selected ? radius + 2 : radius} fillOpacity={0.25 + ((cell.value - valueMin) / valueRange) * 0.75} tabIndex={0} role="button" aria-label={`${rows[cell.row]}, ${columns[cell.column]}, value ${cell.value}, size ${cell.size}`} data-selector={JSON.stringify(selector)} onClick={() => onSelect?.(selector)} onKeyDown={event => activate(event, () => onSelect?.(selector))}><title>{`${rows[cell.row]} / ${columns[cell.column]}: ${cell.value}`}</title></circle>;
    })}
    <text className="figure-note" x="160" y="560">Circle size and opacity represent the supplied values.</text>
  </>;
}

function SequenceFigure({ figure, selectedKey, onSelect }: { figure: ScientificFigureData; selectedKey: string; onSelect?: (selector: FigureSelector) => void }) {
  const features = figure.features ?? [], length = figure.length ?? 1;
  const colors = useCategoryColors(features.map(feature => feature.category));
  const x = (position: number) => 70 + ((position - 1) / Math.max(1, length - 1)) * 630;
  return <>
    <line className="figure-sequence-line" x1="70" x2="700" y1="330" y2="330" />
    {[0, .25, .5, .75, 1].map(fraction => <g key={fraction}><line className="figure-axis" x1={70 + fraction * 630} x2={70 + fraction * 630} y1="321" y2="339" /><text className="figure-tick" x={70 + fraction * 630} y="365" textAnchor="middle">{Math.round(1 + fraction * (length - 1))}</text></g>)}
    {features.map((feature, index) => {
      const selector: FigureSelector = { kind: "feature", id: feature.id };
      const selected = selectedKey === selectorKey(selector);
      const start = x(feature.start), end = x(feature.end), lane = index % 4, y = 76 + lane * 62;
      return <g key={feature.id} className={selected ? "figure-feature selected" : "figure-feature"} tabIndex={0} role="button" aria-label={`${feature.label}, positions ${feature.start} to ${feature.end}`} data-selector={JSON.stringify(selector)} onClick={() => onSelect?.(selector)} onKeyDown={event => activate(event, () => onSelect?.(selector))}>
        <rect x={start} y={y} width={Math.max(5, end - start)} height="28" rx="5" fill={colors.get(feature.category)} />
        {end - start > 58 && <text x={(start + end) / 2} y={y + 18} textAnchor="middle">{feature.label}</text>}
        <title>{`${feature.label}: ${feature.start} to ${feature.end}`}</title>
      </g>;
    })}
    {[...colors].map(([category, color], index) => <g key={category} transform={`translate(${82 + index * 130} 520)`}><rect width="12" height="8" rx="2" fill={color} /><text className="figure-legend" x="19" y="8">{category}</text></g>)}
  </>;
}

function TreeFigure({ figure, selectedKey, onSelect }: { figure: ScientificFigureData; selectedKey: string; onSelect?: (selector: FigureSelector) => void }) {
  const nodes = figure.nodes ?? [];
  const positions = new Map(nodes.map((node, index) => [node.id, { x: 130 + index * (520 / Math.max(1, nodes.length - 1)), y: node.parent_id ? 360 : 160 }]));
  return <>{nodes.filter(node => node.parent_id).map(node => { const child = positions.get(node.id)!; const parent = positions.get(node.parent_id!)!; return <line key={`edge:${node.id}`} className="figure-axis" x1={parent.x} y1={parent.y} x2={child.x} y2={child.y} />; })}{nodes.map(node => { const position = positions.get(node.id)!; const selector: FigureSelector = { kind: "node", id: node.id }; const selected = selectedKey === selectorKey(selector); return <g key={node.id} tabIndex={0} role="button" aria-label={node.label} data-selector={JSON.stringify(selector)} onClick={() => onSelect?.(selector)} onKeyDown={event => activate(event, () => onSelect?.(selector))}><circle className={selected ? "figure-mark selected" : "figure-mark"} cx={position.x} cy={position.y} r={selected ? 10 : 7} /><text className="figure-tick" x={position.x} y={position.y - 16} textAnchor="middle">{node.label}</text></g>; })}</>;
}

export function ScientificFigureWorkbench({ projects, language }: { projects: ProjectOption[] | null; language: Language }) {
  const activeProjects = projects?.filter(project => project.archived_at === null) ?? [];
  const [projectId, setProjectId] = useState("");
  const [name, setName] = useState("scientific-figure");
  const [kind, setKind] = useState<ScientificFigureData["kind"]>("scatter");
  const [source, setSource] = useState(figureTemplates.scatter);
  const [preview, setPreview] = useState<FigurePreview | null>(() => localFigurePreview(figureTemplates.scatter));
  const [selected, setSelected] = useState<FigureSelector | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const next = activeProjects.some(project => project.id === projectId) ? projectId : activeProjects[0]?.id ?? "";
    if (next !== projectId) setProjectId(next);
  }, [activeProjects, projectId]);

  useEffect(() => {
    let active = true;
    invoke<FigurePreview>("render_artifact_preview_development", { mediaType: "application/vnd.shokos.figure+json", content: source })
      .then(result => { if (active) setPreview(result); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [kind]);

  function chooseKind(next: ScientificFigureData["kind"]) {
    setKind(next);
    setSource(figureTemplates[next]);
    setPreview(localFigurePreview(figureTemplates[next]));
    setSelected(null);
    setStatus(null);
    setError(null);
  }

  async function validateSource() {
    return invoke<FigurePreview>("render_artifact_preview_development", { mediaType: "application/vnd.shokos.figure+json", content: source });
  }

  async function renderFigure(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      setPreview(localFigurePreview(source));
      setSelected(null);
    } catch (reason) {
      setPreview(null);
      setError(reason instanceof Error ? reason.message : "FR-RENDERER-FIGURE");
      setBusy(false);
      return;
    }
    try {
      setPreview(await validateSource());
      setSelected(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "FR-RENDERER-FIGURE");
    } finally {
      setBusy(false);
    }
  }

  async function saveFigure() {
    if (!projectId || !name.trim()) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const checked = await validateSource();
      await invoke("create_project_artifact_development", { projectId, name: name.trim(), mediaType: "application/vnd.shokos.figure+json", content: source });
      setPreview(checked);
      setStatus(language === "fr" ? "Figure enregistrée comme artefact versionné." : "Figure saved as a versioned artifact.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "FR-RENDERER-FIGURE-SAVE");
    } finally {
      setBusy(false);
    }
  }

  const figureItemCount = preview?.figure.kind === "scatter" ? preview.figure.points?.length ?? 0 : preview?.figure.kind === "matrix" ? preview.figure.cells?.length ?? 0 : preview?.figure.kind === "tree" ? preview.figure.nodes?.length ?? 0 : preview?.figure.features?.length ?? 0;
  const figureDimension = preview?.figure.kind === "scatter" ? `${new Set(preview.figure.points?.map(point => point.category)).size} families` : preview?.figure.kind === "matrix" ? `${preview.figure.rows?.length ?? 0} × ${preview.figure.columns?.length ?? 0}` : preview?.figure.kind === "tree" ? (language === "fr" ? "topologie" : "topology") : `${preview?.figure.length ?? 0} ${preview?.figure.kind === "genome" ? "bp" : "aa"}`;

  return <section className="figure-workbench">
    <div className="figure-preview-pane">
      {preview ? <>
        <div className={`figure-canvas-shell figure-canvas-${preview.figure.kind}`}><ScientificFigureView figure={preview.figure} selected={selected} onSelect={setSelected} /></div>
        <div className="figure-footer">
          <div className="figure-provenance"><span>{preview.renderer_id}/v{preview.renderer_version}</span><span>{preview.source_sha256 === "pending-engine-validation" ? (language === "fr" ? "Validation moteur en attente" : "Engine validation pending") : `SHA-256 ${preview.source_sha256.slice(0, 12)}`}</span><span>{preview.execution === "disabled" ? (language === "fr" ? "Aucune exécution" : "No execution") : preview.execution}</span></div>
          <div className="figure-selection"><MousePointer2 size={14} /><div><span>{language === "fr" ? "Sélecteur exact" : "Exact selector"}</span><code>{selected ? JSON.stringify(selected) : (language === "fr" ? "Sélectionnez une marque" : "Select a mark")}</code></div></div>
        </div>
      </> : <div className="figure-empty"><ChartScatter size={25} /><h3>{language === "fr" ? "Préparation du canevas" : "Preparing canvas"}</h3><p>{language === "fr" ? "La figure apparaîtra après validation par le moteur local." : "The figure appears after validation by the local engine."}</p></div>}
    </div>
    <aside className="figure-editor" aria-label={language === "fr" ? "Inspecteur de figure" : "Figure inspector"}>
      <div className="figure-editor-heading"><SlidersHorizontal size={16} /><div><h3>{language === "fr" ? "Inspecteur" : "Inspector"}</h3><p>{language === "fr" ? "Figure locale versionnée" : "Versioned local figure"}</p></div></div>
      <form onSubmit={event => void renderFigure(event)}>
        <div className="figure-kind-switch" role="group" aria-label={language === "fr" ? "Type de figure" : "Figure type"}>
          <button type="button" aria-pressed={kind === "scatter"} onClick={() => chooseKind("scatter")}><ChartScatter size={14} />Atlas</button>
          <button type="button" aria-pressed={kind === "matrix"} onClick={() => chooseKind("matrix")}><Grid3x3 size={14} />Matrix</button>
          <button type="button" aria-pressed={kind === "sequence"} onClick={() => chooseKind("sequence")}><Dna size={14} />Sequence</button>
          <button type="button" aria-pressed={kind === "tree"} onClick={() => chooseKind("tree")}><GitBranch size={14} />{language === "fr" ? "Arbre" : "Tree"}</button>
          <button type="button" aria-pressed={kind === "genome"} onClick={() => chooseKind("genome")}><Dna size={14} />Genome</button>
        </div>
        <dl className="figure-summary"><div><dt>{language === "fr" ? "Vue" : "View"}</dt><dd>{preview?.figure.title ?? kind}</dd></div><div><dt>{language === "fr" ? "Marques" : "Marks"}</dt><dd>{figureItemCount}</dd></div><div><dt>{language === "fr" ? "Structure" : "Structure"}</dt><dd>{figureDimension}</dd></div></dl>
        <details className="figure-source-panel">
          <summary><Braces size={14} /><span>{language === "fr" ? "Source JSON" : "JSON source"}</span><small>v1</small></summary>
          <textarea aria-label={language === "fr" ? "Spécification JSON" : "JSON specification"} value={source} onChange={event => { setSource(event.target.value); setStatus(null); }} spellCheck={false} />
        </details>
        <button className="minor-action figure-validate" type="submit" disabled={busy}><Eye size={14} />{language === "fr" ? "Valider avec le moteur" : "Validate with engine"}</button>
      </form>
      <div className="figure-save-row">
        <div className="figure-save-heading"><span>{language === "fr" ? "ARTEFACT" : "ARTIFACT"}</span><p>{language === "fr" ? "Enregistrer la figure validée" : "Save the validated figure"}</p></div>
        <select value={projectId} onChange={event => setProjectId(event.target.value)} aria-label={language === "fr" ? "Projet de destination" : "Destination project"}>{activeProjects.length === 0 && <option value="">{language === "fr" ? "Aucun projet actif" : "No active project"}</option>}{activeProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
        <input value={name} onChange={event => setName(event.target.value)} aria-label={language === "fr" ? "Nom de la figure" : "Figure name"} />
        <button className="minor-action" type="button" onClick={() => void saveFigure()} disabled={busy || !projectId || !name.trim()}><Save size={14} />{language === "fr" ? "Enregistrer" : "Save artifact"}</button>
      </div>
      {error && <div className="inline-error" role="alert"><CircleAlert size={16} /><div><strong>{language === "fr" ? "Figure refusée" : "Figure rejected"}</strong><p>{error}</p></div></div>}
      {status && <p className="figure-status">{status}</p>}
    </aside>
  </section>;
}
