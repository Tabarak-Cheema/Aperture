/**
 * DuckDB-WASM runtime for small datasets (<= ~200 MB).
 *
 * The same compiled SQL plan runs here or on the server. The browser loads
 * data from a local Arrow IPC file (uploaded in-session) and runs filters,
 * paging and grain changes without a round trip.
 *
 * This file is purposefully small; wire it up from Dashboard when the dataset
 * is below the threshold.
 */
import * as duckdb from "@duckdb/duckdb-wasm";

let db: duckdb.AsyncDuckDB | null = null;

export async function getDuckDB(): Promise<duckdb.AsyncDuckDB> {
  if (db) return db;
  const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
  const worker = await duckdb.createWorker(bundle.mainWorker!);
  const logger = new duckdb.ConsoleLogger();
  db = new duckdb.AsyncDuckDB(logger, worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  return db;
}

export async function runLocal(sql: string): Promise<unknown[]> {
  const d = await getDuckDB();
  const conn = await d.connect();
  try {
    const result = await conn.query(sql);
    return result.toArray().map((r) => r.toJSON());
  } finally {
    await conn.close();
  }
}
