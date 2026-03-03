interface CompileShape {
  plan: unknown;
  sql: string | null;
  english: string;
  tier: string;
  tokens_in: number;
  tokens_out: number;
}

interface ResultShape {
  columns: string[];
  rows: unknown[];
  row_count: number;
  latency_ms: number;
  cached: boolean;
  data_version: number;
}

interface Props {
  open: boolean;
  onClose: () => void;
  response?: { compile: CompileShape; result: ResultShape | null };
}

/**
 * Glass-box lineage. Every number is clickable; this drawer shows the plan in
 * English, the compiled SQL, and the result metadata.
 */
export default function LineageDrawer({ open, onClose, response }: Props) {
  if (!open || !response) return null;
  const { compile, result } = response;
  return (
    <aside className="drawer" role="dialog" aria-label="Lineage">
      <header>
        <h3>Lineage</h3>
        <button onClick={onClose} aria-label="Close">×</button>
      </header>

      <section>
        <h4 className="dim small">Plan (English)</h4>
        <p>{compile.english || "—"}</p>
        <h4 className="dim small">Plan (AQIR)</h4>
        <pre>{JSON.stringify(compile.plan, null, 2)}</pre>
      </section>

      <section>
        <h4 className="dim small">Compiled SQL</h4>
        <pre>{compile.sql ?? "— (no plan)"}</pre>
      </section>

      <section>
        <h4 className="dim small">Resolution</h4>
        <dl>
          <dt>Tier</dt><dd>{compile.tier}</dd>
          <dt>Tokens in</dt><dd>{compile.tokens_in}</dd>
          <dt>Tokens out</dt><dd>{compile.tokens_out}</dd>
          {result && (
            <>
              <dt>Data version</dt><dd>v{result.data_version}</dd>
              <dt>Latency</dt><dd>{result.latency_ms} ms{result.cached ? " (cached)" : ""}</dd>
              <dt>Rows</dt><dd>{result.row_count}</dd>
            </>
          )}
        </dl>
      </section>
    </aside>
  );
}
