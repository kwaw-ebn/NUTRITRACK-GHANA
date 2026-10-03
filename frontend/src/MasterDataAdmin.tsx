import { useState, useEffect } from "react";
import { api, post } from "./api";
import { Field, Form, Table, type Row } from "./components";
export default function MasterDataAdmin() {
  const [data, setData] = useState<Row | null>(null),
    [selected, setSelected] = useState<Row | null>(null),
    [error, setError] = useState("");
  const load = () =>
    api<Row>("/api/platform/master-data")
      .then(setData)
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  return (
    <section className="panel">
      <h2>National master data</h2>
      <p>
        Maintain region records with an authoritative source and version.
        Historical operational references are retained; records are deactivated
        rather than deleted.
      </p>
      {error && <p role="alert">{error}</p>}
      {data && (
        <>
          <h3>Regions</h3>
          <Table
            rows={data.regions}
            columns={[
              { key: "name", label: "Region" },
              { key: "region_code", label: "Code" },
              { key: "capital", label: "Capital" },
              {
                key: "manage",
                label: "Manage",
                render: (r) => (
                  <button className="secondary" onClick={() => setSelected(r)}>
                    Versioned update
                  </button>
                ),
              },
            ]}
          />
          {selected && (
            <Form
              key={selected.id}
              onSubmit={async (d) => {
                await post(
                  `/api/platform/master-data/regions/${selected.id}`,
                  { ...d, active: d.active === "true" },
                  "PUT",
                );
                setSelected(null);
                await load();
              }}
            >
              <Field label="Region name">
                <input name="name" required defaultValue={selected.name} />
              </Field>
              <Field label="Region code">
                <input
                  name="region_code"
                  required
                  defaultValue={selected.region_code}
                />
              </Field>
              <Field label="Administrative capital">
                <input name="capital" defaultValue={selected.capital} />
              </Field>
              <Field label="Region status">
                <select
                  name="active"
                  defaultValue={selected.active ? "true" : "false"}
                >
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </Field>
              <Field label="Authoritative source">
                <textarea name="source" required />
              </Field>
              <Field label="Source date">
                <input name="source_date" type="date" required />
              </Field>
              <Field label="Unique import version">
                <input name="version" required />
              </Field>
            </Form>
          )}
          <h3>Health districts</h3>
          <Table
            rows={data.health_districts}
            columns={[
              { key: "name", label: "Health district" },
              {
                key: "region_id",
                label: "Region",
                render: (r) =>
                  data.regions.find((v: Row) => v.id === r.region_id)?.name,
              },
              { key: "source", label: "Source" },
              {
                key: "active",
                label: "Status",
                render: (r) => (r.active ? "Active" : "Inactive"),
              },
              {
                key: "change",
                label: "Manage",
                render: (r) => (
                  <button
                    className="secondary"
                    onClick={async () => {
                      try {
                        await post(
                          `/api/platform/master-data/health-districts/${r.id}/status`,
                          { active: !r.active },
                          "PATCH",
                        );
                        await load();
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    {r.active ? "Deactivate" : "Reactivate"}
                  </button>
                ),
              },
            ]}
          />
          <h3>Master data versions</h3>
          <Table
            rows={data.imports}
            columns={[
              { key: "version", label: "Version" },
              { key: "source_date", label: "Source date" },
              { key: "created_at", label: "Imported at" },
              { key: "imported_by", label: "Imported by" },
              { key: "count", label: "Rows" },
            ]}
          />
        </>
      )}
    </section>
  );
}
