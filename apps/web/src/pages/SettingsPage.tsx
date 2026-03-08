import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, Settings } from "../lib/api";
import { useTheme } from "../lib/theme";

const initial: Partial<Settings> = {};

export default function SettingsPage() {
  const s = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const qc = useQueryClient();
  const { mode, setMode, density, setDensity } = useTheme();
  const [draft, setDraft] = useState<Partial<Settings>>(initial);
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (s.data?.settings && Object.keys(draft).length === 0) {
      setDraft({ provider: s.data.settings.provider, model: s.data.settings.model, ollama_base_url: s.data.settings.ollama_base_url });
    }
  }, [s.data]); // eslint-disable-line

  const save = useMutation({
    mutationFn: (patch: Partial<Settings>) => api.putSettings(patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["health"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    },
  });

  const providers = s.data?.providers ?? [];
  const current = s.data?.settings;
  const selectedProvider = draft.provider ?? current?.provider ?? "ollama";
  const spec = providers.find((p) => p.name === selectedProvider);
  const needsKey = spec?.needs_key ?? false;

  return (
    <div className="page">
      <h2>Settings</h2>
      <p className="dim">Stored locally in <code>~/.aperture/settings.json</code>.</p>

      <section className="card">
        <h3>LLM provider</h3>
        <p className="dim">
          Aperture only calls the LLM for genuinely new questions — most answers come from the cache or local parsing with zero tokens.
        </p>
        <div className="field">
          <label>Provider</label>
          <select
            value={selectedProvider}
            onChange={(e) => setDraft((d) => ({ ...d, provider: e.target.value, model: "" }))}
          >
            {providers.map((p) => (
              <option key={p.name} value={p.name}>{p.label}</option>
            ))}
          </select>
        </div>

        {needsKey && (
          <div className="field">
            <label>API key</label>
            <div className="key-row">
              <input
                type={showKey ? "text" : "password"}
                placeholder={current?.api_key_set ? "●●●●●●  (already set — paste a new key to replace)" : "Paste your API key"}
                value={draft.api_key ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, api_key: e.target.value }))}
                autoComplete="off"
                spellCheck={false}
              />
              <button type="button" onClick={() => setShowKey((v) => !v)}>
                {showKey ? "Hide" : "Show"}
              </button>
            </div>
            <small className="dim">
              Saved locally. Never transmitted anywhere except your chosen provider.
            </small>
          </div>
        )}

        {selectedProvider === "ollama" && (
          <div className="field">
            <label>Ollama base URL</label>
            <input
              value={draft.ollama_base_url ?? current?.ollama_base_url ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, ollama_base_url: e.target.value }))}
              placeholder="http://localhost:11434/v1"
            />
            <small className="dim">
              Start Ollama locally with <code>ollama serve</code> and pull a model, e.g. <code>ollama pull llama3.2</code>.
            </small>
          </div>
        )}

        <div className="field">
          <label>Model <small className="dim">(blank = provider default)</small></label>
          <input
            placeholder={spec?.default_model ?? ""}
            value={draft.model ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, model: e.target.value }))}
          />
        </div>

        <div className="actions">
          <button
            className="primary"
            disabled={save.isPending}
            onClick={() => save.mutate(draft)}
          >
            {save.isPending ? "Saving…" : "Save"}
          </button>
          {saved && <small className="ok">Saved ✓</small>}
        </div>
      </section>

      <section className="card">
        <h3>Appearance</h3>
        <div className="field">
          <label>Theme</label>
          <div className="segmented">
            {(["light", "dark", "system"] as const).map((m) => (
              <button
                key={m}
                className={mode === m ? "active" : ""}
                onClick={() => setMode(m)}
              >
                {m[0].toUpperCase() + m.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <label>Density</label>
          <div className="segmented">
            {(["comfortable", "compact"] as const).map((d) => (
              <button
                key={d}
                className={density === d ? "active" : ""}
                onClick={() => setDensity(d)}
              >
                {d[0].toUpperCase() + d.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
