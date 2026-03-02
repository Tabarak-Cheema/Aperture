import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";
import { useCurrentProject, useProjects } from "./lib/currentProject";
import Brand from "./components/Brand";
import ProjectSwitcher from "./components/ProjectSwitcher";
import ThemeToggle from "./components/ThemeToggle";

const NAV = [
  { to: "/ask",      label: "Ask",      icon: <IconSearch /> },
  { to: "/files",    label: "Files",    icon: <IconFolder /> },
  { to: "/schema",   label: "Schema",   icon: <IconTable /> },
  { to: "/history",  label: "History",  icon: <IconClock /> },
  { to: "/projects", label: "Projects", icon: <IconGrid /> },
  { to: "/settings", label: "Settings", icon: <IconCog /> },
];

export default function App() {
  const [navOpen, setNavOpen] = useState(false);
  const loc = useLocation();
  const nav = useNavigate();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 15_000 });
  const projects = useProjects();
  const { project } = useCurrentProject();

  useEffect(() => setNavOpen(false), [loc.pathname]);
  const needsProject = projects.data && projects.data.projects.length === 0;

  return (
    <div className={`shell ${navOpen ? "nav-open" : ""}`}>
      <header className="topbar">
        <button className="menu-btn" aria-label="Menu" onClick={() => setNavOpen((v) => !v)}>
          <IconMenu />
        </button>
        <div className="top-brand" onClick={() => nav("/ask")}><Brand /></div>
        <div className="top-spacer" />
        <ProjectSwitcher />
        <ThemeToggle />
      </header>

      <aside className="sidebar" aria-label="Primary">
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/ask"}>
              <span className="nav-icon">{n.icon}</span>
              <span className="nav-label">{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-footer">
          <div className="status">
            <span className={`dot ${health.data?.ok ? "dot--ok" : "dot--dim"}`} />
            <span className="dim">{health.data?.ok ? "Online" : "Starting"}</span>
            {health.data?.provider && <span className="chip-tiny">{health.data.provider}</span>}
          </div>
          {project && <small className="dim truncate">in <strong>{project.name}</strong></small>}
        </div>
      </aside>

      <div className="scrim" onClick={() => setNavOpen(false)} aria-hidden />

      <main className="content">
        {needsProject && loc.pathname !== "/projects" && (
          <div className="welcome">
            <div>
              <strong>Welcome.</strong> <span className="dim">Create your first project to get started.</span>
            </div>
            <button className="primary" onClick={() => nav("/projects")}>Create project →</button>
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}

function IconMenu()   { return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>; }
function IconSearch() { return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>; }
function IconFolder() { return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/></svg>; }
function IconTable()  { return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 4v16M15 4v16"/></svg>; }
function IconClock()  { return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>; }
function IconGrid()   { return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>; }
function IconCog()    { return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3h0a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5h0a1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8v0a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/></svg>; }
