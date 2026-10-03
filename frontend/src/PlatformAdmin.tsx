import { useEffect, useState } from "react";
import Setup from "./Setup";
import OrganizationAdmin from "./OrganizationAdmin";
import SystemAdmin from "./SystemAdmin";
import MasterDataAdmin from "./MasterDataAdmin";
import RegistryAdmin from "./RegistryAdmin";
import Intelligence from "./Intelligence";
import StaffAdmin from "./StaffAdmin";
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
    [region, setRegion] = useState(""),
    [section, setSection] = useState("Overview"),
    [setup, setSetup] = useState(false),
    [manage, setManage] = useState(""),
    [invitation, setInvitation] = useState<Row | null>(null);
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
  if (setup)
    return (
      <Setup
        platform
        onBack={() => setSetup(false)}
        onComplete={(r) => {
          setSetup(false);
          setInvitation(r?.invitation || null);
          setManage(r?.organization.id || "");
          setSection("Organizations");
          load();
        }}
      />
    );
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
        <div className="admin-tabs">
          {[
            "Overview",
            "Organizations",
            "Staff & access",
            "Programmes",
            "Indicator standards",
            "Master data",
            "System health",
          ].map((t) => (
            <button
              key={t}
              className={section === t ? "primary" : "secondary"}
              onClick={() => {
                setSection(t);
                setManage("");
              }}
            >
              {t}
            </button>
          ))}
          <button className="primary" onClick={() => setSetup(true)}>
            Add organization
          </button>
        </div>
        {invitation && (
          <div className="notice">
            <div>
              <h3>Secure staff invitation</h3>
              <p>
                {invitation.email} · Expires in {invitation.expires_in_hours}{" "}
                hours. Share privately with this staff member.
              </p>
              <input
                aria-label="Staff invitation link"
                readOnly
                value={invitation.url}
              />
              <button className="secondary" onClick={() => setInvitation(null)}>
                Dismiss invitation
              </button>
            </div>
          </div>
        )}
        {manage && (
          <OrganizationAdmin
            id={manage}
            onClose={() => {
              setManage("");
              load();
            }}
          />
        )}
        {section === "Staff & access" && data && (
          <StaffAdmin
            regions={data.regions}
            organizations={data.organizations}
            onInvitation={setInvitation}
          />
        )}
        {(section === "Programmes" || section === "Indicator standards") && (
          <RegistryAdmin section={section} />
        )}
        {section === "System health" && <SystemAdmin />}
        {section === "Master data" && <MasterDataAdmin />}
        {error && (
          <div role="alert" className="global-error">
            {error}
          </div>
        )}
        {!data && !error && <p>Loading national oversight…</p>}
        {data && ["Overview", "Organizations"].includes(section) && !manage && (
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
            {section === "Overview" && (
              <Intelligence regionId={region || undefined} />
            )}
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
                      key: "manage",
                      label: "Administration",
                      render: (o) => (
                        <button
                          className="secondary"
                          onClick={() => setManage(o.id)}
                        >
                          Manage organization
                        </button>
                      ),
                    },
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
