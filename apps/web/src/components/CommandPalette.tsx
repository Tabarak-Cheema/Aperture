import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, ProjectMeta } from "../lib/api";
import { useRefreshAll } from "../lib/currentProject";
import { useTheme } from "../lib/theme";

interface Cmd { id: string; label: string; hint?: string; group: string; run: () => void; }

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const nav = useNavigate();
  const qc = useQueryClient();
  const refresh = useRefreshAll();
  const { setMode } = useTheme();

  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects, enabled: open });
  const history  = useQuery({ queryKey: ["history", 20], queryFn: () => api.history(20), enabled: open, retry: false });
  const switchP  = useMutation({
    mutationFn: (id: string) => api.switchProject(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["projects"] }); refresh(); },
  });

  // Toggle on cmd/ctrl + K
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault(); setOpen((v) => !v); setQ(""); setActiveIdx(0);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  const commands = useMemo<Cmd[]>(() => {
    const cmds: Cmd[] = [
      { id: "go-ask", group: "Go to", label: "Ask", hint: "/ask", run: () => nav("/ask") },
      { id: "go-files", group: "Go to", label: "Files", hint: "/files", run: () => nav("/files") },
      { id: "go-schema", group: "Go to", label: "Schema", hint: "/schema", run: () => nav("/schema") },
      { id: "go-history", group: "Go to", label: "History", hint: "/history", run: () => nav("/history") },
      { id: "go-projects", group: "Go to", label: "Projects", hint: "/projects", run: () => nav("/projects") },
      { id: "go-settings", group: "Go to", label: "Settings", hint: "/settings", run: () => nav("/settings") },
      { id: "theme-light", group: "Theme", label: "Light theme", run: () => setMode("light") },
      { id: "theme-dark", group: "Theme", label: "Dark theme", run: () => setMode("dark") },
      { id: "theme-system", group: "Theme", label: "System theme", run: () => setMode("system") },
    ];
    for (const p of (projects.data?.projects ?? []) as ProjectMeta[]) {
      const isCurrent = p.id === projects.data?.current_id;
      cmds.push({
        id: `switch-${p.id}`,
        group: "Switch project",
        label: p.name + (isCurrent ? "  (current)" : ""),
        hint: p.path,
        run: () => { if (!isCurrent) switchP.mutate(p.id); setOpen(false); },
      });
    }
    for (const r of (history.data?.history ?? []).slice().reverse().slice(0, 10)) {
      const q = (r as any).question;
      if (!q) continue;
      cmds.push({
        id: `hist-${q}-${(r as any).ts}`,
        group: "Rerun from history",
        label: q,
        hint: (r as any).tier,
        run: () => { nav(`/ask?q=${encodeURIComponent(q)}`); setOpen(false); },
      });
    }
    return cmds;
  }, [projects.data, history.data, nav, setMode, switchP]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(needle) || c.group.toLowerCase().includes(needle));
  }, [q, commands]);

  useEffect(() => { setActiveIdx(0); }, [q]);

  if (!open) return null;

  const grouped: { group: string; items: Cmd[] }[] = [];
  for (const c of filtered) {
    const last = grouped[grouped.length - 1];
    if (last && last.group === c.group) last.items.push(c);
    else grouped.push({ group: c.group, items: [c] });
  }
  const flatIdx = filtered;

  return (
    <div className="palette-scrim" onClick={() => setOpen(false)}>
      <div className="palette" onClick={(e) => e.stopPropagation()}>
        <div className="palette-input">
          <SearchIcon />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Switch project, go to page, rerun a question…"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { e.preventDefault(); setActiveIdx((i) => Math.min(i + 1, flatIdx.length - 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIdx((i) => Math.max(0, i - 1)); }
              else if (e.key === "Enter") { e.preventDefault(); flatIdx[activeIdx]?.run(); setOpen(false); }
            }}
          />
          <kbd className="kbd-corner">ESC</kbd>
        </div>
        <div className="palette-list">
          {flatIdx.length === 0 && <div className="palette-empty">No matches</div>}
          {grouped.map((grp, gi) => (
            <div key={gi} className="palette-group">
              <div className="palette-group-title">{grp.group}</div>
              {grp.items.map((c) => {
                const globalIdx = flatIdx.indexOf(c);
                return (
                  <button
                    key={c.id}
                    className={`palette-item ${globalIdx === activeIdx ? "active" : ""}`}
                    onMouseEnter={() => setActiveIdx(globalIdx)}
                    onClick={() => { c.run(); setOpen(false); }}
                  >
                    <span className="palette-label">{c.label}</span>
                    {c.hint && <span className="palette-hint">{c.hint}</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
        <div className="palette-footer">
          <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
          <span><kbd>↵</kbd> select</span>
          <span><kbd>esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
      <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
    </svg>
  );
}
