/**
 * Client for the local Aperture server.
 *
 * Everything runs on the user's machine; no auth header, no account.
 */

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: {} };
  if (body !== undefined) {
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const r = await fetch(`${BASE}${path}`, init);
  if (!r.ok) throw new Error(`${path} -> ${r.status}: ${await r.text()}`);
  return r.json();
}

export const api = {
  health: () => req<{ ok: boolean; provider: string; current_project_id?: string }>("GET", "/health"),

  // Settings
  getSettings: () =>
    req<{ settings: Settings; providers: ProviderSpec[] }>("GET", "/settings"),
  putSettings: (patch: Partial<Settings>) =>
    req<{ settings: Settings }>("PUT", "/settings", patch),

  // Projects
  listProjects: () =>
    req<{ current_id: string | null; projects: ProjectMeta[] }>("GET", "/projects"),
  createProject: (name: string, path?: string) =>
    req<{ project: ProjectMeta }>("POST", "/projects", { name, path }),
  switchProject: (id: string) =>
    req<{ project: ProjectMeta }>("POST", "/projects/switch", { id }),
  renameProject: (id: string, name: string) =>
    req<{ project: ProjectMeta }>("PATCH", `/projects/${id}`, { name }),
  deleteProject: (id: string, removeFiles = false) =>
    req<{ ok: boolean }>("DELETE", `/projects/${id}?remove_files=${removeFiles}`),

  // Files
  listFiles: () => req<{ files: FileEntry[]; project: string }>("GET", "/files"),
  deleteFile: (name: string) => req<{ ok: boolean }>("DELETE", `/files/${encodeURIComponent(name)}`),
  uploadFile: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`${BASE}/files`, { method: "POST", body: fd });
    if (!r.ok) throw new Error(await r.text());
    return r.json() as Promise<{ table: string; rows: number; columns: string[] }>;
  },

  // Catalog
  getCatalog: () => req<Catalog>("GET", "/catalog"),

  // Ask
  ask: (question: string) => req<AskResponse>("POST", "/ask", { question }),
  history: (limit = 50) => req<{ history: HistoryRecord[] }>("GET", `/history?limit=${limit}`),
  metrics: () => req<{ by_tier: Record<string, number>; total_tokens: number }>("GET", "/metrics"),
};

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------
export interface Settings {
  provider: string;
  api_key: string;
  api_key_set: boolean;
  model: string;
  ollama_base_url: string;
  theme: string;
  density: string;
}

export interface ProviderSpec {
  name: string;
  label: string;
  needs_key: boolean;
  default_model: string;
}

export interface ProjectMeta {
  id: string;
  name: string;
  slug: string;
  path: string;
  created_at: string;
  last_opened_at: string;
}

export interface FileEntry {
  name: string;
  size: number;
  modified: string;
}

export interface Catalog {
  version: number;
  tables: Record<string, {
    name: string;
    primary_key: string[];
    profile: { rows: number; source_path?: string };
    columns: Record<string, {
      name: string;
      type: string;
      description: string;
      profile: {
        distinct: number;
        null_share: number;
        sample_values: string[];
        is_pii: boolean;
        pii_kind: string | null;
      };
    }>;
  }>;
  relationships: unknown[];
}

export interface AQIRPlan {
  metrics: string[];
  dimensions?: string[];
  filters?: { dim: string; op: string; value?: unknown }[];
  time?: { dim: string; range?: string; grain?: string; start?: string; end?: string };
  sort?: { by: string; dir: "asc" | "desc" }[];
  limit?: number;
}

export interface AskResponse {
  ts: string;
  question: string;
  tier: string;
  tokens_in: number;
  tokens_out: number;
  english: string;
  plan: AQIRPlan | null;
  sql: string | null;
  row_count: number;
  latency_ms: number;
  cached: boolean;
  columns?: string[];
  rows?: Record<string, unknown>[];
  note?: string;
  error?: string;
}

export type HistoryRecord = AskResponse;
