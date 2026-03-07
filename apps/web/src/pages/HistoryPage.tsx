import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export default function HistoryPage() {
  const h = useQuery({ queryKey: ["history", 200], queryFn: () => api.history(200) });
  const [filter, setFilter] = useState("");
  const nav = useNavigate();
  const items = (h.data?.history ?? []).slice().reverse();
  const filtered = filter.trim()
    ? items.filter((r) => r.question?.toLowerCase().includes(filter.toLowerCase()))
    : items;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>History</h2>
          <p className="dim">{items.length} question{items.length === 1 ? "" : "s"} asked in this project · newest first.</p>
        </div>
        <input
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ maxWidth: 240 }}
        />
      </div>

      {items.length === 0 && (
        <div className="empty">
          <h3>Nothing asked yet</h3>
          <p className="dim">Head to the <a href="/ask">Ask</a> page and try a question.</p>
        </div>
      )}

      <ul className="history-list">
        {filtered.map((r, i) => (
          <li key={i}>
            <div className="h-head">
              <strong className="h-q">{r.question}</strong>
              <span className="meta-dim">
                <span className={`tier-badge ${["T0","T1","T2"].includes(r.tier) ? "zero" : ""}`}>
                  {r.tier} · {r.tokens_in + r.tokens_out} tok
                </span>
                <span>{r.row_count} rows · {r.latency_ms} ms{r.cached ? " · cached" : ""}</span>
              </span>
            </div>
            {r.english && <p className="h-body">{r.english}</p>}
            {r.sql && <details className="h-sql"><summary className="dim">SQL</summary><pre>{r.sql}</pre></details>}
            {r.error && <p className="error">{r.error}</p>}
            <div className="h-footer">
              <small className="dim">{r.ts?.slice(0, 19).replace("T", " ")}</small>
              <button className="ghost" onClick={() => nav(`/ask?q=${encodeURIComponent(r.question)}`)}>↻ Rerun</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
