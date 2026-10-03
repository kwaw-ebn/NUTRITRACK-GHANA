import IndicatorEditor from "./IndicatorEditor";
import { useEffect, useState } from "react";
import { api, post } from "./api";
import { Field, Form, Select, Table, Badge, type Row } from "./components";

export default function OrganizationAdmin({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<Row | null>(null),
    [error, setError] = useState(""),
    [tab, setTab] = useState("Health structure"),
    [edit, setEdit] = useState<Row | null>(null),
    [preview, setPreview] = useState<Row | null>(null);
  const base = `/api/platform/organizations/${id}`;
  const load = async () => {
    setData(await api(base));
  };
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [id]);
  const save = async (path: string, d: Row, method = "POST") => {
    await post(base + path, d, method);
    setEdit(null);
    await load();
  };
  if (!data) return <p>{error || "Loading organization…"}</p>;
  const c = data.organization.configuration;
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>{data.organization.name}</h2>
        <button className="secondary" onClick={onClose}>
          Close organization management
        </button>
      </div>
      <div className="admin-tabs">
        {[
          "Health structure",
          "Facilities",
          "Communities",
          "Programmes & branding",
          "Indicators",
          "Staff",
        ].map((t) => (
          <button
            key={t}
            className={tab === t ? "primary" : "secondary"}
            onClick={() => {
              setTab(t);
              setEdit(null);
            }}
          >
            {t}
          </button>
        ))}
      </div>
      {error && <p role="alert">{error}</p>}
      {tab === "Health structure" && (
        <>
          <Table
            rows={data.subdistricts}
            columns={[
              { key: "name", label: "Sub-district" },
              { key: "code", label: "Code" },
              { key: "responsible_officer", label: "Responsible officer" },
              {
                key: "active",
                label: "Status",
                render: (r) => (
                  <Badge>{r.active ? "Active" : "Inactive"}</Badge>
                ),
              },
            ]}
          />
          <h3>Add health sub-district</h3>
          <Form onSubmit={(d) => save("/subdistricts", d)}>
            <Field label="Sub-district name">
              <input name="name" required />
            </Field>
            <Field label="Code">
              <input name="code" />
            </Field>
            <Field label="Responsible officer">
              <input name="responsible_officer" />
            </Field>
            <Field label="Contact">
              <input name="contact" />
            </Field>
          </Form>
        </>
      )}
      {tab === "Facilities" && (
        <>
          <Table
            rows={data.facilities}
            columns={[
              { key: "name", label: "Facility" },
              { key: "facility_type", label: "Type" },
              { key: "code", label: "Code" },
              {
                key: "active",
                label: "Status",
                render: (r) => (r.active ? "Active" : "Inactive"),
              },
              {
                key: "edit",
                label: "Manage",
                render: (r) => (
                  <button className="secondary" onClick={() => setEdit(r)}>
                    Edit facility
                  </button>
                ),
              },
            ]}
          />
          <h3>{edit ? "Edit facility" : "Add facility"}</h3>
          <Form
            key={edit?.id || "new"}
            onSubmit={(d) =>
              save(
                edit ? `/facilities/${edit.id}` : "/facilities",
                {
                  ...d,
                  latitude: d.latitude ? Number(d.latitude) : null,
                  longitude: d.longitude ? Number(d.longitude) : null,
                  email: d.email || null,
                  active: d.active === "true",
                  programmes: edit?.programmes || [],
                },
                edit ? "PUT" : "POST",
              )
            }
          >
            <div className="form-grid">
              <Field label="Facility name">
                <input name="name" required defaultValue={edit?.name} />
              </Field>
              <Field label="Facility code">
                <input name="code" defaultValue={edit?.code} />
              </Field>
              <Field label="Facility type">
                <select name="facility_type" defaultValue={edit?.facility_type}>
                  {c.facility_types.map((t: string) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </Field>
              <Field label="Parent sub-district">
                <Select
                  name="subdistrict_id"
                  options={data.subdistricts}
                  defaultValue={edit?.subdistrict_id}
                />
              </Field>
              <Field label="Ownership">
                <input
                  name="ownership"
                  defaultValue={edit?.ownership || "Public"}
                />
              </Field>
              <Field label="Community name">
                <input name="community" defaultValue={edit?.community} />
              </Field>
              <Field label="Latitude">
                <input
                  name="latitude"
                  type="number"
                  step="any"
                  defaultValue={edit?.latitude}
                />
              </Field>
              <Field label="Longitude">
                <input
                  name="longitude"
                  type="number"
                  step="any"
                  defaultValue={edit?.longitude}
                />
              </Field>
              <Field label="Phone">
                <input name="phone" defaultValue={edit?.phone} />
              </Field>
              <Field label="Facility email">
                <input name="email" type="email" defaultValue={edit?.email} />
              </Field>
              <Field label="Facility status">
                <select
                  name="active"
                  defaultValue={edit?.active === false ? "false" : "true"}
                >
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </Field>
            </div>
          </Form>
          <h3>Bulk import facilities</h3>
          <p>
            CSV/XLSX columns: facility_name, facility_code, facility_type,
            subdistrict, community, ownership, latitude, longitude, status.
          </p>
          <input
            aria-label="Import facilities file"
            type="file"
            accept=".csv,.xlsx"
            onChange={async (e) => {
              if (!e.target.files?.[0]) return;
              const fd = new FormData();
              fd.append("file", e.target.files[0]);
              try {
                setPreview(
                  await api(base + "/import/validate", {
                    method: "POST",
                    body: fd,
                  }),
                );
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          />
          {preview && (
            <>
              <p>
                {preview.valid} valid · {preview.invalid} invalid ·{" "}
                {preview.duplicates} duplicates
              </p>
              <Table
                rows={preview.rows.map((r: Row) => ({ ...r, id: r.row }))}
                columns={[
                  { key: "row", label: "Row" },
                  { key: "name", label: "Facility" },
                  { key: "status", label: "Status" },
                  {
                    key: "errors",
                    label: "Errors",
                    render: (r) => r.errors.join("; "),
                  },
                ]}
              />
              <button
                className="primary"
                disabled={
                  !!preview.invalid || !!preview.duplicates || !preview.valid
                }
                onClick={async () => {
                  try {
                    await post(
                      base + "/import",
                      preview.rows.map((r: Row) => r.data),
                    );
                    setPreview(null);
                    await load();
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Import validated facilities
              </button>
              <p>
                Correct invalid or duplicate rows in the source file and upload
                again before saving.
              </p>
            </>
          )}
        </>
      )}
      {tab === "Communities" && (
        <>
          <Table
            rows={data.communities}
            columns={[
              { key: "name", label: "Community" },
              { key: "chps_zone", label: "CHPS zone" },
            ]}
          />
          <h3>Add community / CHPS zone</h3>
          <Form onSubmit={(d) => save("/communities", d)}>
            <Field label="Community name">
              <input name="name" required />
            </Field>
            <Field label="CHPS zone">
              <input name="chps_zone" />
            </Field>
            <Field label="Parent facility">
              <Select name="facility_id" options={data.facilities} />
            </Field>
          </Form>
        </>
      )}
      {tab === "Programmes & branding" && (
        <Form
          onSubmit={(d) =>
            save(
              "/configuration",
              {
                ...d,
                programmes: JSON.parse(d.programmes),
                facility_types: d.facility_types
                  .split(",")
                  .map((v: string) => v.trim())
                  .filter(Boolean),
                quality_weights: JSON.parse(d.quality_weights),
                approval_workflow: d.approval_workflow === "verified"
                  ? ["Draft", "Submitted", "Verified", "Approved", "Locked"]
                  : ["Draft", "Submitted", "Approved", "Locked"],
                report_deadline_day: Number(d.report_deadline_day),
                deterioration_threshold_pp: Number(
                  d.deterioration_threshold_pp,
                ),
                supervision_checklist: d.supervision_checklist
                  .split("\n")
                  .map((v: string) => v.trim())
                  .filter(Boolean),
              },
              "PUT",
            )
          }
        >
          <Field
            label="Enabled programme codes"
            hint={'JSON array, for example ["growth","maternal"]'}
          >
            <textarea
              name="programmes"
              required
              defaultValue={JSON.stringify(c.programmes)}
            />
          </Field>
          <Field label="Data quality component weights" hint="JSON weights: Completeness, Timeliness, Validity; optionally Consistency and Duplicate rate.">
            <textarea name="quality_weights" required defaultValue={JSON.stringify(c.quality_weights || { Completeness: 1, Timeliness: 1, Validity: 1 })} />
          </Field>
          <Field label="Report approval workflow">
            <select name="approval_workflow" defaultValue={(c.approval_workflow || ["Verified"]).includes("Verified") ? "verified" : "direct"}>
              <option value="verified">Submit → Verify → Approve → Lock</option>
              <option value="direct">Submit → Approve → Lock</option>
            </select>
          </Field>
          <Field label="Facility types">
            <input
              name="facility_types"
              required
              defaultValue={c.facility_types.join(", ")}
            />
          </Field>
          <Field label="Deterioration signal threshold (percentage points)">
            <input
              name="deterioration_threshold_pp"
              type="number"
              min="0.1"
              max="100"
              step="0.1"
              defaultValue={c.deterioration_threshold_pp || 5}
            />
          </Field>
          <Field label="Supervision checklist (one question per line)">
            <textarea
              name="supervision_checklist"
              rows={5}
              defaultValue={(c.supervision_checklist || []).join("\n")}
            />
          </Field>
          <Field label="Report header">
            <input
              name="report_header"
              defaultValue={c.report_header || data.organization.name}
            />
          </Field>
          <Field label="Contact details">
            <input name="contact" defaultValue={c.contact} />
          </Field>
          <Field label="Reporting officer">
            <input
              name="reporting_officer"
              defaultValue={c.reporting_officer}
            />
          </Field>
          <Field label="Authorized logo URL">
            <input name="logo_url" type="url" defaultValue={c.logo_url} />
          </Field>
          <Field label="Monthly submission deadline day">
            <input
              name="report_deadline_day"
              type="number"
              min={1}
              max={28}
              defaultValue={c.report_deadline_day || 5}
            />
          </Field>
        </Form>
      )}
      {tab === "Indicators" && (
        <>
          <Table
            rows={data.indicators}
            columns={[
              { key: "name", label: "Indicator" },
              { key: "programme", label: "Programme" },
              { key: "target", label: "Target (%)" },
              { key: "approval_reference", label: "Approval" },
            ]}
          />
          <h3>Add locally approved indicator</h3>
          <IndicatorEditor
            enabled={c.programmes}
            onSave={(d) => save("/indicators", d)}
          />
        </>
      )}
      {tab === "Staff" && (
        <>
          <Table
            rows={data.users}
            columns={[
              { key: "name", label: "Name" },
              { key: "email", label: "Email" },
              { key: "role", label: "Role" },
              { key: "facility_id", label: "Facility scope" },
              { key: "subdistrict_id", label: "Sub-district scope" },
            ]}
          />
          <p>
            Use Staff & access in national administration to add staff or change
            their authorized assignment.
          </p>
        </>
      )}
    </section>
  );
}
