import { useEffect, useState } from "react";
import { api, setTokens } from "./api";
import { Brand, Field, Form, Table, Empty, type Row } from "./components";

export function MainAdminSetup({
  onComplete,
  onBack,
}: {
  onComplete: () => Promise<void>;
  onBack: () => void;
}) {
  return (
    <div className="setup-page">
      <header>
        <Brand />
        <button className="secondary" onClick={onBack}>
          Back to sign in
        </button>
      </header>
      <main>
        <div className="eyebrow">NATIONAL PLATFORM ADMINISTRATION</div>
        <h1>Create main administrator account</h1>
        <p>
          Oversee all regions and health districts. Your account does not
          require a region or district assignment.
        </p>
        <Form
          label="Create main administrator account"
          onSubmit={async (d) => {
            const { setup_token, ...account } = d;
            setTokens(
              await api("/api/platform/setup", {
                method: "POST",
                headers: { "X-Setup-Token": setup_token },
                body: JSON.stringify(account),
              }),
            );
            await onComplete();
          }}
        >
          <Field label="Your name">
            <input name="name" required minLength={2} autoComplete="name" />
          </Field>
          <Field
            label="Owner email"
            hint="Use the platform owner email configured on Render."
          >
            <input name="email" type="email" required autoComplete="email" />
          </Field>
          <Field label="Secure password">
            <input
              name="password"
              type="password"
              required
              minLength={12}
              autoComplete="new-password"
            />
          </Field>
          <Field
            label="Authorized setup token"
            hint="Available in the backend service environment on Render."
          >
            <input
              name="setup_token"
              type="password"
              required
              autoComplete="off"
            />
          </Field>
        </Form>
      </main>
    </div>
  );
}

export default function PlatformAdmin({
  environment,
  onSignOut,
  onOpenOrganization,
}: {
  environment: string;
  onSignOut: () => Promise<void>;
  onOpenOrganization: (id: string) => Promise<void>;
}) {
  const [data, setData] = useState<Row | null>(null),
    [error, setError] = useState(""),
    [region, setRegion] = useState("");
  const load = () =>
    api<Row>("/api/platform/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  const organizations: Row[] =
    data?.organizations.filter((o: Row) => !region || o.region_id === region) ||
    [];
  return (
    <div className="setup-page platform-admin">
      {environment !== "production" && (
        <div className="environment-banner">
          {environment.toUpperCase()} ENVIRONMENT · Use fictional data only
        </div>
      )}
      <header>
        <Brand />
        <button className="secondary" onClick={onSignOut}>
          Sign out
        </button>
      </header>
      <main>
        <div className="eyebrow">MAIN ADMINISTRATOR · GHANA</div>
        <h1>National administration</h1>
        <p>
          Watch all organizations, reporting coverage and platform activity.
          Open a district for its aggregate nutrition dashboard.
        </p>
        {error && (
          <div role="alert" className="global-error">
            {error}
          </div>
        )}
        {!data && !error && <p>Loading national oversight…</p>}
        {data && (
          <>
            <div className="panel">
              <h2>National overview</h2>
              <p>
                {data.regions.length} regions · {data.organizations.length}{" "}
                organizations ·{" "}
                {data.organizations.reduce(
                  (n: number, o: Row) => n + o.facilities,
                  0,
                )}{" "}
                facilities
              </p>
              <Field label="Filter region">
                <select
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                >
                  <option value="">All Ghana — all regions</option>
                  {data.regions.map((r: Row) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </Field>
              <button className="secondary" onClick={load}>
                Refresh overview
              </button>
            </div>
            <div className="panel">
              <h2>Health organizations</h2>
              {organizations.length ? (
                <Table
                  rows={organizations}
                  columns={[
                    { key: "name", label: "Organization" },
                    { key: "region", label: "Region" },
                    { key: "health_district", label: "Health district" },
                    { key: "facilities", label: "Facilities" },
                    { key: "approved_reports", label: "Approved reports" },
                    {
                      key: "open",
                      label: "Dashboard",
                      render: (o) => (
                        <button
                          className="secondary"
                          onClick={() =>
                            onOpenOrganization(o.id).catch((e) =>
                              setError(e.message),
                            )
                          }
                        >
                          Open dashboard
                        </button>
                      ),
                    },
                  ]}
                />
              ) : (
                <Empty
                  title="No organizations in this view"
                  text="District directorates will appear here after completing organization setup."
                />
              )}
            </div>
            <div className="panel">
              <h2>Registered users</h2>
              <Table
                rows={data.users}
                columns={[
                  { key: "name", label: "Name" },
                  { key: "email", label: "Email" },
                  {
                    key: "active",
                    label: "Status",
                    render: (u) => (u.active ? "Active" : "Inactive"),
                  },
                ]}
              />
            </div>
            <div className="panel">
              <h2>System status</h2>
              <p>
                Database: {data.health.database} · Application:{" "}
                {data.health.version} · Migration: {data.health.migration}
              </p>
              <p className="muted">
                Patient records require an explicitly assigned clinical role.
                National oversight provides aggregate access.
              </p>
            </div>
            <div className="panel">
              <h2>Recent audit activity</h2>
              <Table
                rows={data.audit}
                columns={[
                  { key: "event", label: "Event" },
                  { key: "created_at", label: "Time" },
                  { key: "organization_id", label: "Organization ID" },
                ]}
              />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
