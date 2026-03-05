import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";

export default function FilesPage() {
  const qc = useQueryClient();
  const files = useQuery({ queryKey: ["files"], queryFn: api.listFiles });
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = useMutation({
    mutationFn: (f: File) => api.uploadFile(f),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["files"] });
      qc.invalidateQueries({ queryKey: ["catalog"] });
    },
  });
  const del = useMutation({
    mutationFn: (name: string) => api.deleteFile(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["files"] });
      qc.invalidateQueries({ queryKey: ["catalog"] });
    },
  });

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files;
    if (!list) return;
    Array.from(list).forEach((f) => upload.mutate(f));
    e.target.value = "";
  };

  return (
    <div className="page">
      <h2>Files</h2>
      <p className="dim">
        Project: <strong>{files.data?.project ?? "—"}</strong>.
        Supported: .csv, .tsv, .parquet, .xlsx, .xls, .json, .ndjson
      </p>

      <section
        className="dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          Array.from(e.dataTransfer.files).forEach((f) => upload.mutate(f));
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".csv,.tsv,.parquet,.xlsx,.xls,.json,.ndjson"
          style={{ display: "none" }}
          onChange={onPick}
        />
        <strong>Click or drop files here to upload</strong>
        <small className="dim">
          Files are copied into your project folder locally. Nothing uploads to the internet.
        </small>
        {upload.isPending && <small>Uploading…</small>}
      </section>

      <section className="card">
        <h3>In this project ({files.data?.files.length ?? 0})</h3>
        {!files.data?.files.length && <p className="dim">No files yet.</p>}
        <table className="table">
          <thead><tr><th>Name</th><th>Size</th><th>Modified</th><th></th></tr></thead>
          <tbody>
            {files.data?.files.map((f) => (
              <tr key={f.name}>
                <td>{f.name}</td>
                <td>{(f.size / 1024).toFixed(1)} KB</td>
                <td>{f.modified.slice(0, 19).replace("T", " ")}</td>
                <td>
                  <button className="danger" onClick={() => {
                    if (confirm(`Delete ${f.name}?`)) del.mutate(f.name);
                  }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
