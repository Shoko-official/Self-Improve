import { invoke } from "@tauri-apps/api/core";
import { useEffect, useState } from "react";

type CapabilityReport = {
  operatingSystem: string;
  architecture: string;
  logicalCores: number;
  capturedAt: number;
};

const copy = {
  en: {
    title: "Frontier", subtitle: "Local-first AI and scientific workbench",
    probe: "Run hardware probe", unavailable: "Native capability probe is available in the desktop application.",
    areas: ["Workspaces", "Models", "Science", "Artifacts", "Compute", "Settings"]
  },
  fr: {
    title: "Frontier", subtitle: "Atelier IA et scientifique, local par défaut",
    probe: "Lancer la sonde matérielle", unavailable: "La sonde native est disponible dans l’application bureau.",
    areas: ["Espaces", "Modèles", "Science", "Artefacts", "Calcul", "Réglages"]
  }
};

export function App() {
  const [locale, setLocale] = useState<keyof typeof copy>("fr");
  const [report, setReport] = useState<CapabilityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const text = copy[locale];

  async function probe() {
    setError(null);
    try {
      setReport(await invoke<CapabilityReport>("capability_report"));
    } catch {
      setError(text.unavailable);
    }
  }

  useEffect(() => { void probe(); }, []);

  return <main className="shell">
    <aside><div className="brand">{text.title}</div><nav>{text.areas.map(area => <button key={area}>{area}</button>)}</nav></aside>
    <section className="content">
      <header><div><p className="eyebrow">LOCAL FIRST</p><h1>{text.subtitle}</h1></div><button className="locale" onClick={() => setLocale(locale === "fr" ? "en" : "fr")}>{locale === "fr" ? "EN" : "FR"}</button></header>
      <article className="panel"><p className="eyebrow">CAPABILITY EVIDENCE</p><h2>Host capability report</h2>
        {report ? <dl><dt>Operating system</dt><dd>{report.operatingSystem}</dd><dt>Architecture</dt><dd>{report.architecture}</dd><dt>Logical cores</dt><dd>{report.logicalCores}</dd><dt>Captured</dt><dd>{new Date(report.capturedAt * 1000).toLocaleString()}</dd></dl> : <p>{error ?? "Probing host capabilities…"}</p>}
        <button className="primary" onClick={() => void probe()}>{text.probe}</button>
      </article>
      <article className="panel muted"><p className="eyebrow">TRUST BOUNDARY</p><p>Remote providers, storage writes, and external compute require an explicit, scoped approval. No provider fallback is automatic.</p></article>
    </section>
  </main>;
}
