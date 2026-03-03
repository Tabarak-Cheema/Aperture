import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, AskResponse } from "../lib/api";
import Brand from "../components/Brand";
import ChartView from "../components/ChartView";
import LineageDrawer from "../components/LineageDrawer";
import { useCurrentProject } from "../lib/currentProject";

const DEFAULT_SUGGESTIONS = [
  "revenue by region",
  "top 10 country by sales",
  "orders by city",
  "monthly revenue trend",
];

const ZERO_TIERS = new Set(["T0", "T1", "T2"]);

export default function AskPage() {
  const [q, setQ] = useState("");
  const [showLineage, setShowLineage] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const [sp, setSp] = useSearchParams();
  // Rerun from a /ask?q=... URL (used by History + Command Palette)
  useEffect(() => {
    const qp = sp.get("q");
    if (qp) {
      setQ(qp);
      ask.mutate(qp);
      sp.delete("q"); setSp(sp, { replace: true });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp.get("q")]);

  const metrics = useQuery({ queryKey: ["metrics"], queryFn: api.metrics, refetchInterval: 10_000 });
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: api.getCatalog, retry: false });
  const historyQ = useQuery({ queryKey: ["history", 50], queryFn: () => api.history(50), retry: false });
  const { project } = useCurrentProject();

  const ask = useMutation<AskResponse, Error, string>({ mutationFn: (question) => api.ask(question) });

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const inField = target.tagName === "INPUT" || target.tagName === "TEXTAREA";
      if (e.key === "/" && !inField) { e.preventDefault(); inputRef.current?.focus(); }
      if (e.key === "Escape") {
        if (showLineage) setShowLineage(false);
        else if (ask.data || ask.error) ask.reset();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showLineage, ask]);

  const totalTokens = metrics.data?.total_tokens ?? 0;
  const byTier = metrics.data?.by_tier ?? {};
  const totalCalls = Object.values(byTier).reduce((a, n) => a + n, 0);
  const zeroShare = totalCalls === 0 ? 0 : (((byTier.T0 ?? 0) + (byTier.T1 ?? 0) + (byTier.T2 ?? 0)) / totalCalls) * 100;
  const hasResult = !!ask.data || ask.isPending || !!ask.error;
  const isZero = ask.data ? ZERO_TIERS.has(ask.data.tier) && !ask.data.error : false;
  const tableCount = Object.keys(catalog.data?.tables ?? {}).length;

  // Recent unique questions from history (newest first)
  const recentQuestions: string[] = (() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const r of (historyQ.data?.history ?? []).slice().reverse()) {
      const q = (r as any).question?.trim();
      if (q && !seen.has(q.toLowerCase())) { seen.add(q.toLowerCase()); out.push(q); }
      if (out.length >= 5) break;
    }
    return out;
  })();

  const schemaSuggestions: string[] = (() => {
    if (!catalog.data) return [];
    const metricNames: string[] = [];
    const dimNames: string[] = [];
    for (const t of Object.values(catalog.data.tables ?? {})) {
      for (const c of Object.values(t.columns)) {
        if (["number", "integer", "currency", "percent"].includes(c.type)) metricNames.push(c.name);
        else if (["string", "boolean", "date"].includes(c.type) && c.profile.distinct < 50) dimNames.push(c.name);
      }
    }
    const out: string[] = [];
    for (const m of metricNames.slice(0, 2)) {
      for (const d of dimNames.slice(0, 2)) out.push(`${m} by ${d}`);
    }
    return out.slice(0, 4);
  })();

  const primarySuggestions = recentQuestions.length ? recentQuestions
                           : schemaSuggestions.length ? schemaSuggestions
                           : DEFAULT_SUGGESTIONS;

  const submit = (text: string) => { setQ(text); ask.mutate(text); };

  // Result actions
  const copySQL = () => ask.data?.sql && navigator.clipboard.writeText(ask.data.sql);
  const downloadCSV = () => {
    if (!ask.data?.rows || !ask.data.columns) return;
    const esc = (v: unknown) => {
      const s = v == null ? "" : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const header = ask.data.columns.join(",");
    const body = ask.data.rows.map((r) => ask.data!.columns!.map((c) => esc(r[c])).join(",")).join("\n");
    const blob = new Blob([header + "\n" + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url;
    a.download = `${(ask.data.question || "result").replace(/\s+/g, "_")}.csv`;
    a.click(); URL.revokeObjectURL(url);
  };

  return (
    <div className="ask-shell">
      {!hasResult ? (
        <section className="hero">
          <div className="hero-logo"><Brand size={56} withText={false} /></div>
          <h1 className="hero-title">Ask your data.</h1>
          <p className="hero-tag">
            {project
              ? <>in <strong className="project-chip-inline">{project.name}</strong>
                 {tableCount > 0 && <> · {tableCount} {tableCount === 1 ? "table" : "tables"}</>}</>
              : "Local-first analytics. Zero tokens for most questions."}
          </p>
          <AskForm inputRef={inputRef} q={q} setQ={setQ} onSubmit={() => q.trim() && ask.mutate(q)} pending={ask.isPending} />
          {project && tableCount === 0 ? (
            <div className="hero-empty">
              <span className="dim">No data in this project yet.</span>
              <a href="/files" className="btn-link">Upload a file →</a>
            </div>
          ) : (
            <div className="suggestions">
              {recentQuestions.length > 0 && (
                <span className="chip-label">Recent</span>
              )}
              {primarySuggestions.map((s) => (
                <button key={s} className="chip" onClick={() => submit(s)}>{s}</button>
              ))}
            </div>
          )}
        </section>
      ) : (
        <section className="ask-compact">
          <AskForm inputRef={inputRef} q={q} setQ={setQ} onSubmit={() => q.trim() && ask.mutate(q)} pending={ask.isPending} />

          {ask.isPending && (
            <div className="result-card skeleton">
              <div className="skel-line" style={{ width: "40%" }} />
              <div className="skel-line" style={{ width: "80%" }} />
              <div className="skel-line" style={{ width: "66%" }} />
            </div>
          )}

          {ask.error && (
            <article className="result-card result-error">
              <div className="result-head">
                <span className="tier-badge error">error</span>
                <button className="link" onClick={() => ask.reset()}>Dismiss</button>
              </div>
              <p className="error">{ask.error.message}</p>
            </article>
          )}

          {ask.data && (
            <article className={`result-card ${ask.data.error ? "result-error" : ""}`}>
              <div className="result-head">
                <div className="result-meta">
                  <span className={`tier-badge ${isZero ? "zero" : ""}`} title={`Resolution tier ${ask.data.tier}`}>
                    {ask.data.tier} · {ask.data.tokens_in + ask.data.tokens_out} tok
                  </span>
                  <span className="meta-dim">
                    <span>{ask.data.latency_ms} ms</span>
                    {ask.data.cached && <span>· cached</span>}
                    {ask.data.rows && <span>· {ask.data.row_count} rows</span>}
                  </span>
                </div>
                <div className="result-actions">
                  {ask.data.sql && <button className="ghost" onClick={copySQL} title="Copy SQL">⧉ SQL</button>}
                  {ask.data.rows && ask.data.rows.length > 0 && (
                    <button className="ghost" onClick={downloadCSV} title="Download rows as CSV">↓ CSV</button>
                  )}
                  <button className="ghost" onClick={() => ask.mutate(ask.data!.question)} title="Re-run query">↻</button>
                  <button className="link" onClick={() => setShowLineage(true)}>Lineage →</button>
                </div>
              </div>

              {ask.data.error ? (
                <p className="error">{ask.data.error}</p>
              ) : (
                <p className="english">{ask.data.english || ask.data.note || "No plan produced."}</p>
              )}

              {ask.data.rows && ask.data.rows.length > 0 && (
                <ChartView result={{
                  columns: ask.data.columns ?? [],
                  rows: ask.data.rows,
                  row_count: ask.data.row_count,
                  latency_ms: ask.data.latency_ms,
                  cached: ask.data.cached,
                  data_version: 1,
                }} />
              )}
            </article>
          )}

          <div className="suggestions suggestions-inline">
            {primarySuggestions.filter((s) => s !== ask.data?.question).map((s) => (
              <button key={s} className="chip" onClick={() => submit(s)}>{s}</button>
            ))}
          </div>
        </section>
      )}

      <div className="stat-strip">
        <span><b>{totalTokens.toLocaleString()}</b> tokens</span>
        <span className="dot-sep">·</span>
        <span><b>{zeroShare.toFixed(0)}%</b> zero-token</span>
        <span className="dot-sep">·</span>
        <span><b>{totalCalls}</b> answered</span>
        <span className="dot-sep">·</span>
        <span className="kbd-hint"><kbd>/</kbd> focus</span>
      </div>

      <LineageDrawer
        open={showLineage}
        onClose={() => setShowLineage(false)}
        response={ask.data ? { compile: {
          plan: ask.data.plan, sql: ask.data.sql, english: ask.data.english,
          tier: ask.data.tier, tokens_in: ask.data.tokens_in, tokens_out: ask.data.tokens_out,
        }, result: ask.data.rows ? {
          columns: ask.data.columns ?? [], rows: ask.data.rows,
          row_count: ask.data.row_count, latency_ms: ask.data.latency_ms,
          cached: ask.data.cached, data_version: 1,
        } : null } as any : undefined}
      />
    </div>
  );
}

interface AskFormProps {
  q: string; setQ: (v: string) => void;
  onSubmit: () => void; pending: boolean;
  inputRef: React.RefObject<HTMLInputElement>;
}
function AskForm({ q, setQ, onSubmit, pending, inputRef }: AskFormProps) {
  return (
    <form className="ask-box" onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      <SearchIcon />
      <input
        ref={inputRef}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Ask anything about your data…"
        autoFocus
        aria-label="Question"
      />
      <button type="submit" disabled={pending || !q.trim()}>
        {pending ? "…" : "Ask"}
      </button>
    </form>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
      <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
    </svg>
  );
}
