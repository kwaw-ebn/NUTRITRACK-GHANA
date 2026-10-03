import { useEffect, useState } from "react";
import { api, post } from "./api";
import { Field, Form, Select, Table, type Row } from "./components";
export default function StaffAdmin({
  regions,
  organizations,
  onInvitation,
}: {
  regions: Row[];
  organizations: Row[];
  onInvitation: (r: Row) => void;
}) {
  const [data, setData] = useState<Row | null>(null),
    [level, setLevel] = useState("ORGANIZATION"),
    [org, setOrg] = useState(""),
    [structure, setStructure] = useState<Row>({
      subdistricts: [],
      facilities: [],
      communities: [],
    }),
    [sub, setSub] = useState(""),
    [fac, setFac] = useState(""),
    [error, setError] = useState("");
  const load = () =>
    api<Row>("/api/platform/staff")
      .then(setData)
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    setSub("");
    setFac("");
    if (org)
      api<Row>(`/api/platform/organizations/${org}`)
        .then(setStructure)
        .catch((e) => setError(e.message));
    else setStructure({ subdistricts: [], facilities: [], communities: [] });
  }, [org]);
  const roles = [
    "District Nutrition Officer",
    "Nutritionist/Dietitian",
    "Facility In-Charge",
    "Midwife/ANC Staff",
    "Community Health Nurse",
    "School Health/GIFTS Officer",
    "Field/CHPS Worker",
    "Data Officer",
    "Viewer",
  ];
  return (
    <section className="panel">
      <h2>Staff & access</h2>
      <p>
        Assign duties and the smallest required scope. New staff set their own
        passwords using a secure invitation.
      </p>
      {error && <p role="alert">{error}</p>}
      <Form
        label="Assign access"
        onSubmit={async (d) => {
          const result = await post("/api/platform/staff", {
            ...d,
            level,
            organization_id: level === "ORGANIZATION" ? org : null,
            region_id: level === "REGION" ? d.region_id : null,
            subdistrict_id: level === "ORGANIZATION" ? sub || null : null,
            facility_id: level === "ORGANIZATION" ? fac || null : null,
            community_id:
              level === "ORGANIZATION" ? d.community_id || null : null,
          });
          if (result.invitation) onInvitation(result.invitation);
          await load();
        }}
      >
        <div className="form-grid">
          <Field label="Staff name">
            <input name="name" required />
          </Field>
          <Field label="Staff email">
            <input name="email" type="email" required />
          </Field>
          <Field label="Access level">
            <select value={level} onChange={(e) => setLevel(e.target.value)}>
              <option value="NATIONAL">National</option>
              <option value="REGION">Regional</option>
              <option value="ORGANIZATION">
                District / sub-district / facility / community
              </option>
            </select>
          </Field>
          <Field label="Staff role">
            <select name="role" key={level}>
              {(level === "NATIONAL"
                ? ["National Nutrition Administrator"]
                : level === "REGION"
                  ? ["Regional Nutrition Officer"]
                  : roles
              ).map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </Field>
          {level === "REGION" && (
            <Field label="Assigned region">
              <Select name="region_id" options={regions} />
            </Field>
          )}
          {level === "ORGANIZATION" && (
            <>
              <Field label="Assigned health organization">
                <Select
                  name="organization_id"
                  options={organizations}
                  value={org}
                  onChange={setOrg}
                />
              </Field>
              <Field label="Sub-district scope">
                <Select
                  name="subdistrict_id"
                  options={structure.subdistricts}
                  required={false}
                  value={sub}
                  onChange={(v) => {
                    setSub(v);
                    setFac("");
                  }}
                />
              </Field>
              <Field label="Facility scope">
                <Select
                  name="facility_id"
                  required={false}
                  options={structure.facilities.filter(
                    (f: Row) => !sub || f.subdistrict_id === sub,
                  )}
                  value={fac}
                  onChange={setFac}
                />
              </Field>
              <Field label="Community scope">
                <Select
                  name="community_id"
                  required={false}
                  options={structure.communities.filter(
                    (c: Row) => c.facility_id === fac,
                  )}
                />
              </Field>
            </>
          )}
        </div>
      </Form>
      <h3>Staff accounts</h3>
      {data && (
        <>
          <Table
            rows={data.users}
            columns={[
              { key: "name", label: "Name" },
              { key: "email", label: "Email" },
              {
                key: "active",
                label: "Status",
                render: (r) => (r.active ? "Active" : "Inactive"),
              },
              {
                key: "assignments",
                label: "Assigned roles",
                render: (r) =>
                  [
                    ...data.memberships
                      .filter((m: Row) => m.user_id === r.id)
                      .map(
                        (m: Row) =>
                          `${m.role} · ${organizations.find((o) => o.id === m.organization_id)?.name || m.organization_id}`,
                      ),
                    ...data.grants
                      .filter((g: Row) => g.user_id === r.id && g.active)
                      .map(
                        (g: Row) =>
                          `${g.role}${g.region_id ? " · " + regions.find((v) => v.id === g.region_id)?.name : ""}`,
                      ),
                  ].join("; "),
              },
              {
                key: "actions",
                label: "Account actions",
                render: (r) =>
                  data.grants.some(
                    (g: Row) => g.user_id === r.id && g.level === "PLATFORM",
                  ) ? (
                    "Platform owner"
                  ) : (
                    <div className="admin-tabs">
                      <button
                        className="secondary"
                        onClick={async () => {
                          try {
                            await post(
                              `/api/platform/users/${r.id}/status`,
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
                      {r.active && (
                        <button
                          className="secondary"
                          onClick={async () => {
                            try {
                              onInvitation(
                                await post(
                                  `/api/platform/users/${r.id}/invitation`,
                                  {},
                                ),
                              );
                            } catch (e) {
                              setError((e as Error).message);
                            }
                          }}
                        >
                          New setup link
                        </button>
                      )}
                    </div>
                  ),
              },
            ]}
          />
          <h3>Access assignments</h3>
          <Table
            rows={[
              ...data.memberships.map((m: Row) => ({
                ...m,
                kind: "membership",
                level: "ORGANIZATION",
              })),
              ...data.grants
                .filter((g: Row) => g.level !== "PLATFORM")
                .map((g: Row) => ({ ...g, kind: "grant" })),
            ]}
            columns={[
              {
                key: "user_id",
                label: "Staff",
                render: (r) =>
                  data.users.find((u: Row) => u.id === r.user_id)?.name,
              },
              { key: "role", label: "Role" },
              { key: "level", label: "Scope" },
              {
                key: "active",
                label: "Status",
                render: (r) => (r.active ? "Active" : "Revoked"),
              },
              {
                key: "change",
                label: "Access",
                render: (r) => (
                  <button
                    className="secondary"
                    onClick={async () => {
                      try {
                        await post(
                          `/api/platform/assignments/${r.kind}/${r.id}`,
                          { active: !r.active },
                          "PATCH",
                        );
                        await load();
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    {r.active ? "Revoke assignment" : "Restore assignment"}
                  </button>
                ),
              },
            ]}
          />
        </>
      )}
    </section>
  );
}
