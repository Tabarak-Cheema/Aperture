import { useEffect, useMemo, useRef, useState } from "react";
import embed, { VisualizationSpec } from "vega-embed";

export interface ResultShape {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  latency_ms: number;
  cached: boolean;
  data_version: number;
}

type ChartType = "auto" | "bar" | "line" | "area" | "table";

/** Pro-grade chart view with:
 *   - brand-matched palette (resolved at render time from CSS vars)
 *   - number formatting with thousands separators
 *   - chart-type picker: bar / line / area / table
 *   - responsive sizing (width:container, min height based on data)
 */
export default function ChartView({ result }: { result: ResultShape }) {
  const ref = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<ChartType>("auto");

  const inferred = useMemo<Exclude<ChartType, "auto">>(() => {
    const cols = result.columns;
    if (cols.includes("period")) return "line";
    if (cols.length >= 2 && result.rows.length > 1) return "bar";
    return "table";
  }, [result]);

  const effective: Exclude<ChartType, "auto"> = mode === "auto" ? inferred : mode;

  useEffect(() => {
    if (!ref.current || effective === "table") return;
    const cs = getComputedStyle(document.documentElement);
    const accent    = cs.getPropertyValue("--accent").trim() || "#6366f1";
    const brandG1   = cs.getPropertyValue("--brand-g1").trim() || "#5eead4";
    const brandG2   = cs.getPropertyValue("--brand-g2").trim() || "#6366f1";
    const textDim   = cs.getPropertyValue("--text-dim").trim() || "#8891a8";
    const textCol   = cs.getPropertyValue("--text").trim() || "#e7ecf4";
    const grid      = cs.getPropertyValue("--border").trim() || "#22263a";

    const spec = buildSpec(result, effective, { accent, brandG1, brandG2, textDim, textCol, grid });
    embed(ref.current, spec, { actions: false, renderer: "svg" }).catch(() => {});
  }, [result, effective]);

  return (
    <div className="chart-shell">
      <div className="chart-toolbar">
        <div className="segmented sm">
          {(["auto", "bar", "line", "area", "table"] as const).map((t) => (
            <button key={t} className={mode === t ? "active" : ""} onClick={() => setMode(t)}>{t}</button>
          ))}
        </div>
        <span className="dim small">
          {result.row_count} rows{result.cached ? " · cached" : ""}
        </span>
      </div>
      {effective !== "table" && <div ref={ref} className="chart" />}
      {effective === "table" && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>{result.columns.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {result.rows.map((row, i) => (
                <tr key={i}>
                  {result.columns.map((c) => (
                    <td key={c} className={typeof row[c] === "number" ? "num" : ""}>
                      {formatValue(row[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function formatValue(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") {
    if (Number.isInteger(v)) return v.toLocaleString();
    return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return String(v);
}

interface Palette {
  accent: string; brandG1: string; brandG2: string;
  textDim: string; textCol: string; grid: string;
}

function buildSpec(
  result: ResultShape,
  kind: "bar" | "line" | "area",
  p: Palette,
): VisualizationSpec {
  const cols = result.columns;
  const hasPeriod = cols.includes("period");
  const xField = hasPeriod ? "period" : cols[0];
  const yField = cols[cols.length - 1];
  const xType: "temporal" | "nominal" = hasPeriod ? "temporal" : "nominal";

  const config = {
    background: "transparent",
    font: 'Inter, system-ui, sans-serif',
    axis: {
      labelColor: p.textDim, titleColor: p.textCol,
      gridColor: p.grid, domainColor: p.grid, tickColor: p.grid,
      labelFontSize: 11, titleFontSize: 11, titleFontWeight: 500,
      titlePadding: 12, grid: true,
      labelPadding: 4,
    },
    axisX: hasPeriod ? {} : { labelAngle: -20, labelLimit: 160 },
    view: { stroke: "transparent" },
    legend: { labelColor: p.textDim, titleColor: p.textCol },
    padding: { top: 8, right: 8, bottom: 8, left: 8 },
  };

  const mark: any = kind === "bar"
    ? { type: "bar", color: p.accent, cornerRadiusEnd: 3 }
    : kind === "line"
    ? { type: "line", point: { filled: true, size: 36 }, color: p.accent, strokeWidth: 2.5 }
    : { type: "area", color: p.accent, line: true, opacity: 0.85 };

  const yFormat = ",.0f";

  return {
    data: { values: result.rows },
    mark,
    encoding: {
      x: { field: xField, type: xType, sort: kind === "bar" ? "-y" : undefined,
           axis: { title: xField } },
      y: { field: yField, type: "quantitative",
           axis: { title: yField, format: yFormat } },
      tooltip: cols.map((c) => ({
        field: c,
        type: typeof result.rows[0]?.[c] === "number" ? "quantitative" : "nominal",
        ...(typeof result.rows[0]?.[c] === "number" ? { format: ",.2f" } : {}),
      })),
    },
    width: "container",
    height: 340,
    config,
  } as VisualizationSpec;
}
