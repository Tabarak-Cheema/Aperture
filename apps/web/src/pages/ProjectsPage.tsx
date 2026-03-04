import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useRefreshAll } from "../lib/currentProject";

export default function ProjectsPage() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const qc = useQueryClient();
  const refresh = useRefreshAll();

  const create = useMutation({
    mutationFn: () => api.createProject(name.trim(), path.trim() || undefined),
    onSuccess: () => { setName(""); setPath(""); qc.invalidateQueries({ queryKey: ["projects"] }); refresh(); },
  });
  const sw = useMutation({
    mutationFn: (id: string) => api.switchProject(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["projects"] }); refresh(); },
  });
  const rename = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api.renameProject(id, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
  const del = useMutation({
    mutationFn: ({ id, remove }: { id: string; remove: boolean }) => api.deleteProject(id, remove),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["projects"] }); refresh(); },
  });

  return (
    <div className="page">
      <h2>Projects</h2>
      <p className="dim">Each project is a local folder. Files, catalog, plan cache and history live inside it.</p>

      <section className="card">
        <h3>Create project</h3>
        <form
          onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(); }}
          className="create-project"
        >
          <input
            placeholder="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            aria-label="Project name"
          />
          <input
            placeholder="Optional folder path — defaults to ~/.aperture/projects/<slug>"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            aria-label="Project folder path"
          />
          <button className="primary" type="submit" disabled={create.isPending || !name.trim()}>
            {create.isPending ? "Creating…" : "Create"}
          </button>
        </form>
      </section>

      <section className="card">
        <h3>All projects</h3>
        {!projects.data?.projects.length && <p className="dim">No projects yet.</p>}
        <ul className="project-list">
          {projects.data?.projects.map((p) => {
            const current = p.id === projects.data.current_id;
            return (
              <li key={p.id} className={current ? "current" : ""}>
                <div className="pcol">
                  <strong>{p.name}</strong>
                  <small className="dim">{p.path}</small>
                  <small className="dim">Created {p.created_at.slice(0, 10)}</small>
                </div>
                <div className="pactions">
                  {!current && (
                    <button onClick={() => sw.mutate(p.id)}>Switch to</button>
                  )}
                  <button
                    onClick={() => {
                      const n = prompt("New name", p.name);
                      if (n && n !== p.name) rename.mutate({ id: p.id, name: n });
                    }}
                  >Rename</button>
                  <button
                    className="danger"
                    onClick={() => {
                      const removeFiles = confirm(`Delete "${p.name}"?\n\nOK = also delete the folder on disk\nCancel = keep the folder`);
                      del.mutate({ id: p.id, remove: removeFiles });
                    }}
                  >Delete</button>
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
