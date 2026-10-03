import { useState, useEffect } from "react";
import { api, post, download } from "./api";
import { Field, Form, Select, Table, Modal, type Row } from "./components";
export default function Supervision({
  facilities,
  checklist,
  canManage,
}: {
  facilities: Row[];
  checklist: string[];
  canManage: boolean;
}) {
  const [records, setRecords] = useState<Row[]>([]),
    [selected, setSelected] = useState<Row | null>(null),
    [open, setOpen] = useState(false),
    [filter, setFilter] = useState(""),
    [evidence, setEvidence] = useState<Row[]>([]),
    [error, setError] = useState("");
  const load = () =>
    api<Row[]>("/api/registers/supervision")
      .then(setRecords)
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  const select = async (r: Row) => {
    setSelected(r);
    setOpen(true);
    try {
      setEvidence(await api(`/api/supervision/${r.id}/evidence`));
    } catch {
      setEvidence([]);
    }
  };
  const questions = selected?.details.checklist_snapshot || checklist;
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Supportive supervision</h2>
          <p>
            Schedule visits, compare findings and follow corrective actions.
          </p>
        </div>
        {canManage && (
          <button
            className="primary"
            onClick={() => {
              setSelected(null);
              setEvidence([]);
              setOpen(true);
            }}
          >
            Schedule supervision
          </button>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      <Field label="Compare visits at facility">
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All assigned facilities</option>
          {facilities.map((f) => (
            <option value={f.id} key={f.id}>
              {f.name}
            </option>
          ))}
        </select>
      </Field>
      <Table
        rows={records
          .filter((r) => !filter || r.facility_id === filter)
          .sort((a, b) => b.details.date.localeCompare(a.details.date))}
        columns={[
          { key: "title", label: "Visit" },
          {
            key: "facility_id",
            label: "Facility",
            render: (r) => facilities.find((f) => f.id === r.facility_id)?.name,
          },
          { key: "date", label: "Date", render: (r) => r.details.date },
          {
            key: "status",
            label: "Status",
            render: (r) => r.details.status || "Completed",
          },
          {
            key: "findings",
            label: "Findings",
            render: (r) => r.details.findings || "Awaiting visit",
          },
          {
            key: "checklist",
            label: "Checklist findings",
            render: (r) =>
              Object.entries(r.details.checklist_answers || {})
                .map(([k, v]) => `${k}: ${v}`)
                .join("; "),
          },
          {
            key: "manage",
            label: "Details",
            render: (r) => (
              <button className="secondary" onClick={() => select(r)}>
                Review visit
              </button>
            ),
          },
        ]}
      />
      {open && (
        <Modal
          title={
            selected
              ? "Review supportive supervision"
              : "Schedule supportive supervision"
          }
          onClose={() => setOpen(false)}
        >
          {canManage ? (
            <Form
              onSubmit={async (d) => {
                const answers: Row = {};
                questions.forEach((q: string, i: number) => {
                  answers[q] = d[`question_${i}`];
                  delete d[`question_${i}`];
                });
                const { title, facility_id, ...details } = d;
                await post(
                  selected
                    ? `/api/registers/supervision/${selected.id}`
                    : "/api/registers/supervision",
                  {
                    title,
                    facility_id,
                    details: {
                      ...details,
                      checklist_answers: answers,
                      checklist_snapshot: questions,
                    },
                  },
                  selected ? "PUT" : "POST",
                );
                setOpen(false);
                await load();
              }}
            >
              <Field label="Visit title">
                <input name="title" required defaultValue={selected?.title} />
              </Field>
              <Field label="Supervision facility">
                <Select
                  name="facility_id"
                  options={facilities}
                  defaultValue={selected?.facility_id}
                />
              </Field>
              <Field label="Visit date">
                <input
                  name="date"
                  type="date"
                  required
                  defaultValue={
                    selected?.details.date ||
                    new Date().toISOString().slice(0, 10)
                  }
                />
              </Field>
              <Field label="Visit status">
                <select
                  name="status"
                  defaultValue={selected?.details.status || "Scheduled"}
                >
                  <option>Scheduled</option>
                  <option>Completed</option>
                  <option>Cancelled</option>
                </select>
              </Field>
              {questions.map((q: string, i: number) => (
                <Field key={q} label={q}>
                  <select
                    name={`question_${i}`}
                    defaultValue={
                      selected?.details.checklist_answers?.[q] ||
                      "Not applicable"
                    }
                  >
                    <option>Yes</option>
                    <option>No</option>
                    <option>Not applicable</option>
                  </select>
                </Field>
              ))}
              <Field label="Visit findings (required when completed)">
                <textarea
                  name="findings"
                  defaultValue={selected?.details.findings}
                />
              </Field>
              <Field label="Corrective action">
                <input
                  name="corrective_action"
                  defaultValue={selected?.details.corrective_action}
                />
              </Field>
              <Field label="Follow-up deadline">
                <input
                  name="followup_date"
                  type="date"
                  defaultValue={selected?.details.followup_date}
                />
              </Field>
            </Form>
          ) : (
            <p>{selected?.details.findings}</p>
          )}
          {selected && (
            <>
              <h3>Authorized evidence</h3>
              <p>
                Attach approved PDF, PNG or JPEG evidence, up to 2 MB. Follow
                your organization's rules for confidential information.
              </p>
              {canManage && (
                <input
                  type="file"
                  aria-label="Supervision evidence file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={async (e) => {
                    if (!e.target.files?.[0]) return;
                    const fd = new FormData();
                    fd.append("file", e.target.files[0]);
                    try {
                      await api(`/api/supervision/${selected.id}/evidence`, {
                        method: "POST",
                        body: fd,
                      });
                      setEvidence(
                        await api(`/api/supervision/${selected.id}/evidence`),
                      );
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                />
              )}
              <Table
                rows={evidence}
                columns={[
                  { key: "filename", label: "Evidence" },
                  { key: "size_bytes", label: "Bytes" },
                  {
                    key: "download",
                    label: "Open",
                    render: (r) => (
                      <button
                        className="secondary"
                        onClick={() =>
                          download(
                            `/api/evidence/${r.id}/download`,
                            r.filename,
                          ).catch((e) => setError(e.message))
                        }
                      >
                        Download evidence
                      </button>
                    ),
                  },
                ]}
              />
            </>
          )}
        </Modal>
      )}
    </section>
  );
}
