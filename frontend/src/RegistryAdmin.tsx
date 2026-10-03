import { useState, useEffect } from "react";
import { api, post } from "./api";
import { Field, Form, Table, type Row } from "./components";
export default function RegistryAdmin({
  section,
}: {
  section: "Programmes" | "Indicator standards";
}) {
  const [programmes, setProgrammes] = useState<Row[]>([]),
    [standards, setStandards] = useState<Row[]>([]),
    [selected, setSelected] = useState<Row | null>(null),
    [error, setError] = useState("");
  const load = async () => {
    setProgrammes(await api("/api/platform/programmes"));
    setStandards(await api("/api/indicator-standards"));
  };
  useEffect(() => {
    load().catch((e) => setError(e.message));
    setSelected(null);
  }, [section]);
  return (
    <section className="panel">
      <h2>{section}</h2>
      {error && <p role="alert">{error}</p>}
      {section === "Programmes" ? (
        <>
          <p>
            Enable future programmes through configuration. Capture fields are
            versioned; existing encounters preserve the template used at entry.
          </p>
          <Table
            rows={programmes}
            columns={[
              { key: "name", label: "Programme" },
              { key: "code", label: "Code" },
              { key: "schema_version", label: "Template version" },
              {
                key: "active",
                label: "Status",
                render: (r) => (r.active ? "Active" : "Inactive"),
              },
              {
                key: "edit",
                label: "Manage",
                render: (r) => (
                  <button className="secondary" onClick={() => setSelected(r)}>
                    Edit programme
                  </button>
                ),
              },
            ]}
          />
          <h3>{selected ? "Edit programme" : "Register programme"}</h3>
          <Form
            key={selected?.id || "new"}
            onSubmit={async (d) => {
              await post(
                selected
                  ? `/api/platform/programmes/${selected.id}`
                  : "/api/platform/programmes",
                {
                  ...d,
                  active: d.active === "true",
                  fields: JSON.parse(d.fields),
                },
                selected ? "PUT" : "POST",
              );
              setSelected(null);
              await load();
            }}
          >
            <Field label="Programme code">
              <input
                name="code"
                required
                pattern="[a-z][a-z0-9-]{1,59}"
                defaultValue={selected?.code}
                readOnly={!!selected}
              />
            </Field>
            <Field label="Programme name">
              <input name="name" required defaultValue={selected?.name} />
            </Field>
            <Field label="Programme status">
              <select
                name="active"
                defaultValue={selected?.active === false ? "false" : "true"}
              >
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
            </Field>
            <Field
              label="Capture fields (JSON)"
              hint={
                'Example: [{"key":"service_given","label":"Service provided","type":"boolean","required":false}]. Types: number, text, date, boolean, select, school.'
              }
            >
              <textarea
                name="fields"
                rows={9}
                required
                defaultValue={JSON.stringify(selected?.fields || [], null, 2)}
              />
            </Field>
            <Field label="Template approval reference">
              <input
                name="approval_reference"
                defaultValue={selected?.approval_reference}
              />
            </Field>
          </Form>
        </>
      ) : (
        <>
          <p>
            Register authorized definitions with a source, version and approval
            reference. A changed definition requires a new version, preserving
            historical comparisons.
          </p>
          <Table
            rows={standards}
            columns={[
              { key: "code", label: "Code" },
              { key: "name", label: "Indicator" },
              { key: "version", label: "Version" },
              { key: "approval_reference", label: "Approval" },
            ]}
          />
          <h3>Add shared indicator definition</h3>
          <Form
            onSubmit={async (d) => {
              await post("/api/platform/indicator-standards", {
                ...d,
                target: d.target ? Number(d.target) : null,
              });
              await load();
            }}
          >
            <div className="form-grid">
              <Field label="Standard indicator code">
                <input name="code" required pattern="[A-Z][A-Z0-9_]{1,59}" />
              </Field>
              <Field label="Definition version">
                <input name="version" required />
              </Field>
              <Field label="Indicator name">
                <input name="name" required />
              </Field>
              <Field label="Programme">
                <select name="programme">
                  {programmes
                    .filter((p) => p.active)
                    .map((p) => (
                      <option key={p.code} value={p.code}>
                        {p.name}
                      </option>
                    ))}
                </select>
              </Field>
            </div>
            <Field label="Operational definition">
              <textarea name="definition" required />
            </Field>
            <Field label="Numerator definition">
              <textarea name="numerator_definition" required />
            </Field>
            <Field label="Denominator definition">
              <textarea name="denominator_definition" required />
            </Field>
            <Field label="National target (%) if approved">
              <input name="target" type="number" step="any" min={0} max={100} />
            </Field>
            <Field label="Desired direction">
              <select name="direction">
                <option value="higher">Higher is better</option>
                <option value="lower">Lower is better</option>
              </select>
            </Field>
            <Field label="Approval reference">
              <input name="approval_reference" required />
            </Field>
            <Field label="Authoritative source URL">
              <input name="source_url" type="url" required />
            </Field>
          </Form>
        </>
      )}
    </section>
  );
}
