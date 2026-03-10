import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useCurrentProject } from "../lib/currentProject";

export default function SchemaPage() {
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: api.getCatalog, retry: false });
  const { project } = useCurrentProject();
  const [selected, setSelected] = useState<string | null>(null);

  const tables = Object.values(catalog.data?.tables ?? {});
  const relationships = (catalog.data?.relationships ?? []) as any[];
  const current = selected
    ? catalog.data?.tables[selected]
    : tables[0];

  // Derive counts for the overview strip
  const overview = useMemo(() => {
    let cols = 0, rows = 0, piiCols = 0, metrics = 0, dims = 0;
    for (const t of tables) {
      rows += t.profile.rows;
      for (const c of Object.values(t.columns)) {
        cols += 1;
        if (c.profile.is_pii) piiCols += 1;
        if (["number", "integer", "currency", "percent"].includes(c.type)) metrics += 1;
        else if (["string", "boolean", "date"].includes(c.type)) dims += 1;
      }
    }
    return { cols, rows, piiCols, metrics, dims };
  }, [tables]);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>Schema</h2>
          <p className="dim">
            {project ? <>Project <strong>{project.name}</strong> · v{catalog.data?.version ?? 0}</> : "No project open"}
          </p>
        </div>
      </div>

      {tables.length === 0 ? (
        <div className="empty">
          <h3>Nothing to profile yet</h3>
          <p className="dim">Upload CSV, Excel, Parquet or JSON files on the <a href="/files">Files</a> page and Aperture will auto-detect types, PII, candidate keys and relationships.</p>
        </div>
      ) : (
        <>
          <div className="overview-strip">
            <StatTile label="Tables"  value={tables.length} />
            <StatTile label="Columns" value={overview.cols} />
            <StatTile label="Rows"    value={overview.rows.toLocaleString()} />
            <StatTile label="Metrics" value={overview.metrics} hint="Numeric columns usable as sums/averages" />
            <StatTile label="Dimensions" value={overview.dims} hint="Categorical / date columns usable for grouping" />
            <StatTile label="Joins" value={relationships.length} />
            {overview.piiCols > 0 && <StatTile label="PII" value={overview.piiCols} tone="warn" />}
          </div>

          <div className="split-pane">
            <ul className="tablelist">
              {tables.map((t) => (
                <li key={t.name} className={current?.name === t.name ? "selected" : ""} onClick={() => setSelected(t.name)}>
                  <strong>{t.name}</strong>
                  <small>{t.profile.rows.toLocaleString()} rows · {Object.keys(t.columns).length} cols</small>
                </li>
              ))}
            </ul>
            <div className="profile-pane">
              {current && (
                <>
                  <div className="profile-head">
                    <h3>{current.name}</h3>
                    {current.primary_key.length > 0 && (
                      <span className="pk-badge">PK: <code>{current.primary_key.join(", ")}</code></span>
                    )}
                  </div>
                  {current.profile.source_path && (
                    <p className="dim small">Source: <code>{current.profile.source_path.split(/[/\\]/).pop()}</code></p>
                  )}
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Column</th><th>Type</th><th style={{ textAlign: "right" }}>Distinct</th>
                        <th style={{ textAlign: "right" }}>Null</th><th>Sample</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.values(current.columns).map((c) => (
                        <tr key={c.name}>
                          <td>
                            <strong>{c.name}</strong>
                            {c.profile.is_pii && <span className="pii">{c.profile.pii_kind ?? "PII"}</span>}
                          </td>
                          <td><code>{c.type}</code></td>
                          <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                            {c.profile.distinct.toLocaleString()}
                          </td>
                          <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                            {(c.profile.null_share * 100).toFixed(0)}%
                          </td>
                          <td className="dim small truncate" style={{ maxWidth: 260 }}>
                            {c.profile.sample_values.slice(0, 3).join(", ")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          </div>

          {relationships.length > 0 && (
            <section className="card" style={{ marginTop: 24 }}>
              <h3>Relationships</h3>
              <p className="dim">Discovered automatically from column containment, name similarity and type match.</p>
              <table className="table">
                <thead><tr><th>Left</th><th>Right</th><th>Cardinality</th><th>Confidence</th></tr></thead>
                <tbody>
                  {relationships.map((r, i) => (
                    <tr key={i}>
                      <td><code>{r.left_table}.{r.left_column}</code></td>
                      <td><code>{r.right_table}.{r.right_column}</code></td>
                      <td>{r.cardinality}</td>
                      <td style={{ fontVariantNumeric: "tabular-nums" }}>{Math.round((r.confidence ?? 0) * 100)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function StatTile({ label, value, hint, tone }: { label: string; value: number | string; hint?: string; tone?: "warn" }) {
  return (
    <div className={`stat-tile ${tone ?? ""}`} title={hint}>
      <strong>{value}</strong>
      <small>{label}</small>
    </div>
  );
}
