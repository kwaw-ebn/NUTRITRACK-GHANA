import { useEffect, useState } from "react";
import { api, post } from "./api";
import { Field, Form, Select, Table, Empty, type Row } from "./components";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
export default function Intelligence({
  organizationId,
  regionId,
  onOpenOrganization,
  canAct = false,
}: {
  organizationId?: string;
  regionId?: string;
  onOpenOrganization?: (id: string) => void;
  canAct?: boolean;
}) {
  const [data, setData] = useState<Row | null>(null),
    [period, setPeriod] = useState(() => {
      const d = new Date();
      d.setMonth(d.getMonth() - 1);
      return d.toISOString().slice(0, 7);
    }),
    [error, setError] = useState(""),
    [standard, setStandard] = useState(""),
    [selected, setSelected] = useState<Row | null>(null),
    [team, setTeam] = useState<Row[]>([]),
    [facilities, setFacilities] = useState<Row[]>([]),
    [notice, setNotice] = useState("");
  const load = () => {
    const p = new URLSearchParams({ period });
    if (organizationId) p.set("organization_id", organizationId);
    if (regionId) p.set("region_id", regionId);
    return api<Row>(`/api/intelligence?${p}`)
      .then(setData)
      .catch((e) => setError(e.message));
  };
  useEffect(() => {
    setError("");
    load();
  }, [period, organizationId, regionId]);
  const trends = (data?.trends || []).filter((r: Row) => r.id === standard);
  return (
    <section className="panel intelligence">
      <div className="panel-heading">
        <div>
          <h2>Nutrition intelligence</h2>
          <p>Data → Signal → Action → Follow-up → Outcome</p>
        </div>
        <Field label="Analysis month">
          <input
            type="month"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          />
        </Field>
      </div>
      {error && <p role="alert">{error}</p>}
      {notice && <p className="notice">{notice}</p>}
      {data && (
        <>
          <div className="review-grid">
            <div>
              <small>Expected facilities</small>
              <strong>{data.expected_facilities}</strong>
            </div>
            <div>
              <small>Submitted facilities</small>
              <strong>{data.submitted_facilities}</strong>
            </div>
            <div>
              <small>Approved reports</small>
              <strong>{data.approved_reports}</strong>
            </div>
            <div>
              <small>Indicator signals</small>
              <strong>{data.signals.length}</strong>
            </div>
          </div>
          <h3>Reporting and district priorities</h3>
          <Table
            rows={data.organizations}
            columns={[
              { key: "name", label: "Health organization" },
              { key: "region", label: "Region" },
              {
                key: "reporting_completeness",
                label: "Reporting completeness",
                render: (r) =>
                  r.reporting_completeness == null
                    ? "No denominator"
                    : `${r.reporting_completeness}%`,
              },
              {
                key: "approved_completeness",
                label: "Approved completeness",
                render: (r) =>
                  r.approved_completeness == null
                    ? "No denominator"
                    : `${r.approved_completeness}%`,
              },
              { key: "open_signals", label: "Signals" },
              ...(onOpenOrganization
                ? [
                    {
                      key: "open",
                      label: "Dashboard",
                      render: (r: Row) => (
                        <button
                          className="secondary"
                          onClick={() => onOpenOrganization(r.id)}
                        >
                          Open dashboard
                        </button>
                      ),
                    },
                  ]
                : []),
            ]}
          />
          <h3>Comparable indicator trends</h3>
          <Field label="Shared indicator definition">
            <select
              value={standard}
              onChange={(e) => setStandard(e.target.value)}
            >
              <option value="">Select a shared indicator…</option>
              {data.standards.map((s: Row) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.code} · version {s.version}
                </option>
              ))}
            </select>
          </Field>
          {trends.length ? (
            <div style={{ height: 240 }}>
              <ResponsiveContainer>
                <LineChart data={trends}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="period" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="value"
                    name="Coverage (%)"
                    stroke="#287459"
                    connectNulls={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <Empty
              title="No comparable trend yet"
              text="Link district indicators to an approved shared definition, then approve monthly reports."
            />
          )}
          {standard && (
            <Table
              rows={data.regional_comparison
                .filter((r: Row) => r.id === standard)
                .map((r: Row) => ({ ...r, id: r.region_id }))}
              columns={[
                { key: "region", label: "Region" },
                { key: "numerator", label: "Numerator" },
                { key: "denominator", label: "Denominator" },
                { key: "value", label: "Coverage (%)" },
              ]}
            />
          )}
          <h3>Signals requiring review</h3>
          {data.signals.length ? (
            <Table
              rows={data.signals}
              columns={[
                { key: "organization", label: "Organization" },
                { key: "title", label: "Indicator" },
                { key: "kind", label: "Signal" },
                { key: "value", label: "Current (%)" },
                { key: "target", label: "Target (%)" },
                { key: "change_pp", label: "Change (pp)" },
                { key: "stockout_days", label: "Recorded stock-out days" },
                { key: "action_status", label: "Action status" },
                ...(canAct
                  ? [
                      {
                        key: "respond",
                        label: "Response",
                        render: (r: Row) => (
                          <button
                            className="secondary"
                            disabled={!!r.action_id}
                            onClick={async () => {
                              setSelected(r);
                              try {
                                const [users, structure] = await Promise.all([api<Row[]>("/api/users"), api<Row>("/api/structure")]);
                                setTeam(users);
                                setFacilities(structure.facilities);
                              } catch (e) { setError((e as Error).message); }
                            }}
                          >
                            Assign action
                          </button>
                        ),
                      },
                    ]
                  : []),
              ]}
            />
          ) : (
            <p>
              No target gaps or deterioration signals in approved data for this
              month.
            </p>
          )}
          {selected && (
            <Form
              label="Assign signal action"
              onSubmit={async (d) => {
                await post("/api/signals/actions", {
                  ...d,
                  facility_id: d.facility_id || null,
                  indicator_id: selected.indicator_id,
                  period: selected.period,
                });
                setSelected(null);
                setNotice(
                  "Action assigned. Track completion and record the observed outcome in the action centre.",
                );
                await load();
              }}
            >
              <h3>
                {selected.title} — {selected.kind}
              </h3>
              <Field label="Why this needs attention and proposed response">
                <textarea
                  name="problem"
                  required
                  minLength={10}
                  defaultValue={selected.explanation}
                />
              </Field>
              <Field label="Facility for this action (optional)">
                <select name="facility_id"><option value="">District-wide action</option>{facilities.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}</select>
              </Field>
              <Field label="Responsible officer">
                <Select name="assigned_to" options={team} />
              </Field>
              <Field label="Action deadline">
                <input name="due_date" type="date" required />
              </Field>
            </Form>
          )}
          <p className="muted">{data.methodology}</p>
        </>
      )}
    </section>
  );
}
