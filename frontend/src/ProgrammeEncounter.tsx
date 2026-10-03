import { useState, useEffect } from "react";
import { api } from "./api";
import { Form, Field, Select, type Row } from "./components";
export default function ProgrammeEncounter({
  registry,
  enabled,
  clients,
  initial,
  role,
  onSave,
}: {
  registry: Row[];
  enabled: string[];
  clients: Row[];
  initial?: string;
  role: string;
  onSave: (d: Row) => Promise<void>;
}) {
  const allowed = enabled.filter((k) =>
    role === "Midwife/ANC Staff"
      ? k === "maternal"
      : role === "School Health/GIFTS Officer"
        ? k === "gifts"
        : ["Community Health Nurse", "Field/CHPS Worker"].includes(role)
          ? ["growth", "iycf", "vitamin-a"].includes(k)
          : true,
  );
  const [programme, setProgramme] = useState(initial || allowed[0] || ""),
    [schools, setSchools] = useState<Row[]>([]),
    [client, setClient] = useState("");
  const definition = registry.find((r) => r.code === programme);
  useEffect(() => {
    if (programme === "gifts")
      api<Row[]>("/api/registers/schools")
        .then(setSchools)
        .catch(() => {});
  }, [programme]);
  const fields = definition?.fields || [];
  return (
    <Form
      onSubmit={async (d) => {
        const measurements: Row = {};
        for (const f of fields) {
          const v = d[`capture_${f.key}`];
          if (v !== "") {
            measurements[f.key] =
              f.type === "number"
                ? Number(v)
                : f.type === "boolean"
                  ? v === "true"
                  : v;
          }
          delete d[`capture_${f.key}`];
        }
        await onSave({
          ...d,
          programme,
          client_id: client,
          measurements,
          followup_date: d.followup_date || null,
        });
      }}
    >
      <div className="form-grid">
        <Field label="Client">
          <Select
            name="client_id"
            options={clients}
            value={client}
            onChange={setClient}
          />
        </Field>
        <Field label="Programme">
          <select
            value={programme}
            onChange={(e) => setProgramme(e.target.value)}
          >
            {allowed.map((k) => (
              <option key={k} value={k}>
                {registry.find((p) => p.code === k)?.name || k}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Visit date">
          <input
            name="visit_date"
            type="date"
            required
            defaultValue={new Date().toISOString().slice(0, 10)}
            max={new Date().toISOString().slice(0, 10)}
          />
        </Field>
        {fields.map((f: Row) => (
          <Field key={`${programme}:${f.key}`} label={f.label}>
            {f.type === "boolean" || f.type === "select" ? (
              <select name={`capture_${f.key}`} required={f.required}>
                <option value="">Not recorded</option>
                {f.type === "boolean" ? (
                  <>
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                  </>
                ) : (
                  f.options.map((o: string) => <option key={o}>{o}</option>)
                )}
              </select>
            ) : f.type === "school" ? (
              <Select
                name={`capture_${f.key}`}
                required={f.required}
                options={schools
                  .filter(
                    (s) =>
                      s.facility_id ===
                      clients.find((c) => c.id === client)?.facility_id,
                  )
                  .map((s) => ({ ...s, name: s.title }))}
              />
            ) : (
              <input
                name={`capture_${f.key}`}
                type={
                  f.type === "number"
                    ? "number"
                    : f.type === "date"
                      ? "date"
                      : "text"
                }
                required={f.required}
                min={f.min}
                max={f.max}
                step="any"
                maxLength={2000}
              />
            )}
          </Field>
        ))}
        <Field label="Staff-assessed priority">
          <select name="risk">
            {["Routine", "Needs assessment", "High", "Immediate"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </Field>
        <Field label="Follow-up date">
          <input name="followup_date" type="date" />
        </Field>
      </div>
      <Field label="Nutrition assessment and services provided">
        <textarea name="assessment" required minLength={2} maxLength={4000} />
      </Field>
      <Field label="Outcome / advice">
        <textarea name="outcome" maxLength={2000} />
      </Field>
      <p className="muted">
        Capture template version {definition?.schema_version || 1}. Clinical
        assessment remains the responsibility of authorized staff.
      </p>
    </Form>
  );
}
