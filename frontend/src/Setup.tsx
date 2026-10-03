import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Plus,
  MapPin,
  ShieldCheck,
  Building2,
} from "lucide-react";
import { api, setTokens } from "./api";
import IndicatorEditor from "./IndicatorEditor";
import { Brand, Field, Combobox, Table, type Row } from "./components";
const steps = [
  "Organization",
  "Location",
  "Health structure",
  "Facilities",
  "Administrator",
  "Programmes",
  "Targets",
  "Review",
];
export default function Setup({
  onComplete,
  onBack,
  platform = false,
}: {
  onComplete: (result?: Row) => void;
  platform?: boolean;
  onBack: () => void;
}) {
  const [step, setStep] = useState(0),
    [regions, setRegions] = useState<Row[]>([]),
    [programmes, setProgrammes] = useState<Row[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [importPreview, setImportPreview] = useState<Row | null>(null);
  const [data, setData] = useState<Row>({
    name: "",
    organization_type: "District Health Directorate",
    region_id: "",
    health_district_name: "",
    subdistricts: [{ name: "", code: "" }],
    facilities: [],
    admin_name: "",
    admin_email: "",
    password: "",
    programmes: [],
    contact: "",
    indicators: [],
  });
  const [token, setToken] = useState("");
  const update = (key: string, value: any) =>
    setData({ ...data, [key]: value });
  useEffect(() => {
    Promise.all([
      api<Row[]>("/api/geography/regions"),
      api<Row[]>("/api/programmes"),
    ])
      .then(([r, p]) => {
        setRegions(r);
        setProgrammes(p);
      })
      .catch((e) => setError(e.message));
  }, []);
  const next = () => {
    setError("");
    if (step === 0 && data.name.length < 3)
      return setError("Enter the organization name.");
    if (
      step === 1 &&
      (!data.region_id || data.health_district_name.trim().length < 2)
    )
      return setError("Choose a region and enter your health district.");
    if (
      step === 2 &&
      data.subdistricts.some((s: Row) => s.name.trim().length < 2)
    )
      return setError("Name each health sub-district.");
    if (
      step === 3 &&
      data.facilities.some((f: Row) => !f.name || !f.subdistrict_id)
    )
      return setError("Complete each facility or remove it.");
    if (
      step === 4 &&
      (!data.admin_name ||
        !data.admin_email ||
        (!platform && data.password.length < 12))
    )
      return setError(
        "Provide administrator details and a password of at least 12 characters.",
      );
    if (step === 5 && !data.programmes.length)
      return setError("Select at least one programme.");
    setStep(step + 1);
  };
  return (
    <div className="setup-page">
      <header>
        <Brand />
        <button className="text-button" onClick={onBack}>
          <ArrowLeft size={16} />
          {platform ? "Back to national administration" : "Back to sign in"}
        </button>
      </header>
      <main>
        <div className="eyebrow">YOUR DISTRICT. ONE CONNECTED WORKSPACE.</div>
        <h1>Set Up Your NutriTrack Organization</h1>
        <p className="muted">
          Configure your health structure once. Build a clearer picture of
          nutrition, every day.
        </p>
        <div className="steps">
          {steps.map((s, i) => (
            <button
              key={s}
              disabled={i > step}
              onClick={() => setStep(i)}
              className={i === step ? "current" : i < step ? "done" : ""}
            >
              <span>{i < step ? <Check size={14} /> : i + 1}</span>
              {s}
            </button>
          ))}
        </div>
        <section className="setup-card">
          <div className="section-heading">
            <span className="step-icon">
              {step < 2 ? (
                <MapPin />
              ) : step === 4 ? (
                <ShieldCheck />
              ) : (
                <Building2 />
              )}
            </span>
            <div>
              <small>
                STEP {step + 1} OF {steps.length}
              </small>
              <h2>{steps[step]}</h2>
            </div>
          </div>
          {step === 0 && (
            <div className="form-grid">
              <Field label="Organization name">
                <input
                  value={data.name}
                  onChange={(e) => update("name", e.target.value)}
                  placeholder="Your District Health Directorate"
                />
              </Field>
              <Field label="Organization type">
                <select
                  value={data.organization_type}
                  onChange={(e) => update("organization_type", e.target.value)}
                >
                  {[
                    "District Health Directorate",
                    "Regional Health Directorate",
                    "Health Facility",
                    "Ghana Health Service",
                    "Pilot/Research Organization",
                  ].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </Field>
              <Field label="Contact details">
                <input
                  value={data.contact}
                  onChange={(e) => update("contact", e.target.value)}
                  placeholder="Office phone or email"
                />
              </Field>
            </div>
          )}
          {step === 1 && (
            <div className="form-grid">
              <Field label="Country">
                <input value="Ghana" readOnly />
              </Field>
              <Field label="Region">
                <Combobox
                  options={regions}
                  value={data.region_id}
                  onChange={(v) =>
                    setData({ ...data, region_id: v, health_district_name: "" })
                  }
                  placeholder="Select Region"
                />
              </Field>
              <Field
                label="Health district"
                hint="Enter the health-service district name approved by your directorate."
              >
                <input
                  value={data.health_district_name}
                  onChange={(e) =>
                    update("health_district_name", e.target.value)
                  }
                  placeholder="Type your health district"
                />
              </Field>
            </div>
          )}
          {step === 2 && (
            <>
              <p className="muted">
                Enter your health sub-districts. Health structures are managed
                locally.
              </p>
              {data.subdistricts.map((s: Row, i: number) => (
                <div className="inline-fields" key={i}>
                  <input
                    aria-label={`Sub-district ${i + 1}`}
                    placeholder="Health sub-district name"
                    value={s.name}
                    onChange={(e) =>
                      update(
                        "subdistricts",
                        data.subdistricts.map((v: Row, j: number) =>
                          i === j ? { ...v, name: e.target.value } : v,
                        ),
                      )
                    }
                  />
                  <input
                    aria-label="Sub-district code"
                    placeholder="Code (optional)"
                    value={s.code}
                    onChange={(e) =>
                      update(
                        "subdistricts",
                        data.subdistricts.map((v: Row, j: number) =>
                          i === j ? { ...v, code: e.target.value } : v,
                        ),
                      )
                    }
                  />
                  {data.subdistricts.length > 1 && (
                    <button
                      onClick={() =>
                        update(
                          "subdistricts",
                          data.subdistricts.filter(
                            (_: Row, j: number) => i !== j,
                          ),
                        )
                      }
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
              <button
                className="secondary"
                onClick={() =>
                  update("subdistricts", [
                    ...data.subdistricts,
                    { name: "", code: "" },
                  ])
                }
              >
                <Plus size={16} />
                Add another sub-district
              </button>
            </>
          )}
          {step === 3 && (
            <>
              <p className="muted">
                Add facilities now, or use validated CSV/XLSX bulk import from
                Administration after setup.
              </p>
              {data.facilities.map((f: Row, i: number) => (
                <div className="inline-fields" key={i}>
                  <input
                    aria-label="Facility name"
                    placeholder="Facility name"
                    value={f.name}
                    onChange={(e) =>
                      update(
                        "facilities",
                        data.facilities.map((v: Row, j: number) =>
                          i === j ? { ...v, name: e.target.value } : v,
                        ),
                      )
                    }
                  />
                  <select
                    aria-label="Facility type"
                    value={f.facility_type}
                    onChange={(e) =>
                      update(
                        "facilities",
                        data.facilities.map((v: Row, j: number) =>
                          i === j ? { ...v, facility_type: e.target.value } : v,
                        ),
                      )
                    }
                  >
                    {[
                      "Hospital",
                      "Polyclinic",
                      "Health Centre",
                      "CHPS",
                      "Clinic",
                      "Maternity Home",
                      "Other",
                    ].map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                  <select
                    aria-label="Parent sub-district"
                    value={f.subdistrict_id}
                    onChange={(e) =>
                      update(
                        "facilities",
                        data.facilities.map((v: Row, j: number) =>
                          i === j
                            ? { ...v, subdistrict_id: e.target.value }
                            : v,
                        ),
                      )
                    }
                  >
                    <option value="">Sub-district…</option>
                    {data.subdistricts.map((s: Row) => (
                      <option key={s.name}>{s.name}</option>
                    ))}
                  </select>
                  <button
                    onClick={() =>
                      update(
                        "facilities",
                        data.facilities.filter((_: Row, j: number) => i !== j),
                      )
                    }
                  >
                    Remove
                  </button>
                </div>
              ))}
              <h3>Bulk import facilities</h3>
              <p>
                CSV/XLSX: facility_name, facility_code, facility_type,
                subdistrict, community, ownership, latitude, longitude, status.
              </p>
              <input
                type="file"
                aria-label="Setup facility import file"
                accept=".csv,.xlsx"
                onChange={async (e) => {
                  if (!e.target.files?.[0]) return;
                  const fd = new FormData();
                  fd.append("file", e.target.files[0]);
                  fd.append(
                    "subdistricts",
                    JSON.stringify(data.subdistricts.map((s: Row) => s.name)),
                  );
                  try {
                    setImportPreview(
                      await api("/api/setup/facilities/validate", {
                        method: "POST",
                        body: fd,
                      }),
                    );
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              />
              {importPreview && (
                <>
                  <p>
                    {importPreview.valid} valid · {importPreview.invalid}{" "}
                    invalid · {importPreview.duplicates} duplicates
                  </p>
                  <Table
                    rows={importPreview.rows}
                    columns={[
                      { key: "row", label: "Row" },
                      { key: "name", label: "Facility" },
                      { key: "status", label: "Status" },
                      {
                        key: "errors",
                        label: "Issues",
                        render: (r) => r.errors.join("; "),
                      },
                    ]}
                  />
                  <button
                    className="secondary"
                    disabled={
                      !!importPreview.invalid ||
                      !!importPreview.duplicates ||
                      !importPreview.valid
                    }
                    onClick={() => {
                      update("facilities", [
                        ...data.facilities,
                        ...importPreview.rows.map((r: Row) => r.data),
                      ]);
                      setImportPreview(null);
                    }}
                  >
                    Use validated facilities
                  </button>
                  <p>
                    Correct errors in the source file and upload again before
                    proceeding.
                  </p>
                </>
              )}
              <button
                className="secondary"
                onClick={() =>
                  update("facilities", [
                    ...data.facilities,
                    { name: "", facility_type: "CHPS", subdistrict_id: "" },
                  ])
                }
              >
                <Plus size={16} />
                Add health facility
              </button>
            </>
          )}
          {step === 4 && (
            <div className="form-grid">
              <Field label="Administrator name">
                <input
                  value={data.admin_name}
                  onChange={(e) => update("admin_name", e.target.value)}
                  autoComplete="name"
                />
              </Field>
              <Field label="Email">
                <input
                  type="email"
                  value={data.admin_email}
                  onChange={(e) => update("admin_email", e.target.value)}
                  autoComplete="email"
                />
              </Field>
              {!platform && (
                <>
                  <Field
                    label="Secure password"
                    hint="At least 12 characters. Share through a secure channel."
                  >
                    <input
                      type="password"
                      value={data.password}
                      onChange={(e) => update("password", e.target.value)}
                      autoComplete="new-password"
                    />
                  </Field>
                  <Field
                    label="Authorized setup token"
                    hint="Provided by the platform operator to authorize organization creation."
                  >
                    <input
                      type="password"
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      autoComplete="off"
                    />
                  </Field>
                </>
              )}
              {platform && (
                <p className="notice">
                  New administrators receive a single-use password setup link.
                  Existing accounts keep their password and receive an explicit
                  district administrator assignment.
                </p>
              )}
            </div>
          )}
          {step === 5 && (
            <div className="programme-grid">
              {programmes.map((p) => (
                <label
                  className={`programme-option ${data.programmes.includes(p.code) ? "selected" : ""}`}
                  key={p.id}
                >
                  <input
                    type="checkbox"
                    checked={data.programmes.includes(p.code)}
                    onChange={(e) =>
                      update(
                        "programmes",
                        e.target.checked
                          ? [...data.programmes, p.code]
                          : data.programmes.filter((v: string) => v !== p.code),
                      )
                    }
                  />
                  <span>{p.name}</span>
                </label>
              ))}
            </div>
          )}
          {step === 6 && (
            <>
              <p>
                Add approved indicators and targets now, or configure them after
                setup. NutriTrack does not invent local targets.
              </p>
              <Table
                rows={data.indicators.map((i: Row, n: number) => ({
                  ...i,
                  id: n,
                }))}
                columns={[
                  { key: "name", label: "Indicator" },
                  { key: "target", label: "Target (%)" },
                  { key: "approval_reference", label: "Approval" },
                ]}
              />
              <IndicatorEditor
                enabled={data.programmes}
                onSave={async (d) => {
                  update("indicators", [...data.indicators, d]);
                }}
              />
            </>
          )}
          {step === 7 && (
            <>
              <div className="review-grid">
                {[
                  ["Organization", data.name],
                  [
                    "Region",
                    regions.find((r) => r.id === data.region_id)?.name,
                  ],
                  ["Health district", data.health_district_name],
                  [
                    "Health sub-districts",
                    data.subdistricts.map((s: Row) => s.name).join(", "),
                  ],
                  ["Facilities", data.facilities.length || "Add after setup"],
                  ["Administrator", data.admin_name],
                  [
                    "Programmes",
                    programmes
                      .filter((p) => data.programmes.includes(p.code))
                      .map((p) => p.name)
                      .join(", "),
                  ],
                ].map(([k, v]) => (
                  <div key={k}>
                    <small>{k}</small>
                    <strong>{v}</strong>
                  </div>
                ))}
              </div>
              <p className="muted">
                NutriTrack Ghana is an independent product. Configure authorized
                organization branding after setup.
              </p>
            </>
          )}
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <div className="setup-footer">
            <button
              className="secondary"
              disabled={step === 0 || busy}
              onClick={() => setStep(step - 1)}
            >
              <ArrowLeft size={16} />
              Previous
            </button>
            {step < 7 ? (
              <button className="primary" onClick={next}>
                Continue
                <ArrowRight size={17} />
              </button>
            ) : (
              <button
                className="primary"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  try {
                    const result = await api(
                      platform ? "/api/platform/organizations" : "/api/setup",
                      {
                        method: "POST",
                        headers: platform ? {} : { "X-Setup-Token": token },
                        body: JSON.stringify(
                          platform ? { ...data, password: null } : data,
                        ),
                      },
                    );
                    if (!platform) setTokens(result);
                    onComplete(result);
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {busy ? "Creating workspace…" : "Complete organization setup"}
                <Check size={17} />
              </button>
            )}
          </div>
        </section>
        <p className="setup-note">
          Secure by design • Organization isolation • Auditable configuration
        </p>
      </main>
    </div>
  );
}
