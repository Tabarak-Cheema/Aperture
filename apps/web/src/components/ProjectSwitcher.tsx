import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useProjects, useRefreshAll } from "../lib/currentProject";

export default function ProjectSwitcher() {
  const projects = useProjects();
  const refreshAll = useRefreshAll();
  const qc = useQueryClient();
  const sw = useMutation({
    mutationFn: (id: string) => api.switchProject(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      refreshAll();
    },
  });
  const list = projects.data?.projects ?? [];
  if (list.length === 0) return <span className="dim small">No project</span>;
  return (
    <select
      className="project-select"
      value={projects.data?.current_id ?? ""}
      onChange={(e) => sw.mutate(e.target.value)}
      aria-label="Switch project"
    >
      {list.map((p) => (
        <option key={p.id} value={p.id}>{p.name}</option>
      ))}
    </select>
  );
}
