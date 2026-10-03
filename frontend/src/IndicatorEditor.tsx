import { useEffect, useState } from "react";
import { api } from "./api";
import { Field, Form, type Row } from "./components";
export default function IndicatorEditor({
  enabled,
  onSave,
}: {
  enabled: string[];
  onSave: (d: Row) => Promise<void>;
}) {
  const [standards, setStandards] = useState<Row[]>([]),
    [selected, setSelected] = useState("");
  useEffect(() => {
    api<Row[]>("/api/indicator-standards")
      .then(setStandards)
      .catch(() => {});
  }, []);
  const standard = standards.find((s) => s.id === selected);
  return (
    <>
      <Field label="Use shared indicator definition">
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">Local indicator only</option>
          {standards
            .filter((s) => enabled.includes(s.programme))
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} · {s.code} · {s.version}
              </option>
            ))}
        </select>
      </Field>
      <Form
        key={selected}
        onSubmit={(d) =>
          onSave({
            ...d,
            standard_id: selected || null,
            target: Number(d.target),
            programme: standard?.programme || d.programme,
          })
        }
      >
        <Field label="Indicator name">
          <input
            name="name"
            required
            readOnly={!!standard}
            defaultValue={standard?.name}
          />
        </Field>
        <Field label="Programme">
          <select name="programme" defaultValue={standard?.programme}>
            {enabled.map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
        </Field>
        <Field label="Operational definition">
          <textarea
            name="definition"
            required
            readOnly={!!standard}
            defaultValue={standard?.definition}
          />
        </Field>
        <Field label="Numerator definition">
          <textarea
            name="numerator_definition"
            required
            readOnly={!!standard}
            defaultValue={standard?.numerator_definition}
          />
        </Field>
        <Field label="Denominator definition">
          <textarea
            name="denominator_definition"
            required
            readOnly={!!standard}
            defaultValue={standard?.denominator_definition}
          />
        </Field>
        <Field label="Approved target (%)">
          <input
            name="target"
            required
            type="number"
            min={0}
            max={100}
            step="any"
            defaultValue={standard?.target ?? ""}
          />
        </Field>
        <Field label="Desired direction">
          <select
            name="direction"
            defaultValue={standard?.direction || "higher"}
          >
            <option value="higher">Higher is better</option>
            <option value="lower">Lower is better</option>
          </select>
        </Field>
        <Field label="Approval reference">
          <input
            name="approval_reference"
            required
            defaultValue={standard?.approval_reference}
          />
        </Field>
      </Form>
    </>
  );
}
