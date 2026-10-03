import { useEffect, useState } from "react";
import { api } from "./api";
import { Table, type Row } from "./components";
export default function SystemAdmin() {
  const [data, setData] = useState<Row | null>(null),
    [error, setError] = useState("");
  const load = () =>
    api<Row>("/api/platform/system")
      .then(setData)
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  return (
    <section className="panel">
      <h2>System health & releases</h2>
      <button className="secondary" onClick={load}>
        Refresh system status
      </button>
      {error && <p role="alert">{error}</p>}
      {data && (
        <>
          <Table
            rows={Object.entries(data.health).map(([key, value]) => ({
              id: key,
              name: key.replaceAll("_", " "),
              value:
                typeof value === "object"
                  ? JSON.stringify(value)
                  : String(value ?? "Not verified"),
            }))}
            columns={[
              { key: "name", label: "Check" },
              { key: "value", label: "Status" },
            ]}
          />
          <h3>Report generation queue</h3>
          <Table
            rows={data.jobs}
            columns={[
              { key: "state", label: "Status" },
              { key: "format", label: "Format" },
              { key: "created_at", label: "Queued at" },
              { key: "error", label: "Issue" },
            ]}
          />
          <h3>What's New in NutriTrack</h3>
          {data.releases.map((r: Row) => (
            <article key={r.version}>
              <h4>
                Version {r.version} · {r.date} · Migration {r.migration}
              </h4>
              <ul>
                {r.features.map((f: string) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              <p>{r.status}</p>
            </article>
          ))}
        </>
      )}
    </section>
  );
}
