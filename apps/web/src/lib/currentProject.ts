import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ProjectMeta } from "./api";

export function useProjects() {
  return useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
}

export function useCurrentProject(): { project: ProjectMeta | null; isLoading: boolean } {
  const q = useProjects();
  if (!q.data) return { project: null, isLoading: q.isLoading };
  const current = q.data.projects.find((p) => p.id === q.data.current_id) ?? null;
  return { project: current, isLoading: false };
}

export function useRefreshAll() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["projects"] });
    qc.invalidateQueries({ queryKey: ["files"] });
    qc.invalidateQueries({ queryKey: ["catalog"] });
    qc.invalidateQueries({ queryKey: ["history"] });
    qc.invalidateQueries({ queryKey: ["metrics"] });
  };
}
