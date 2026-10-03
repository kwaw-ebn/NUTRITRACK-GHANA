import { useState, useEffect, useCallback, useRef } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Bell,
  Building2,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  ClipboardList,
  Download,
  FileText,
  HeartPulse,
  LayoutDashboard,
  Leaf,
  LogOut,
  MapPin,
  Menu,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Target,
  Users,
  WifiOff,
  X,
  Package,
  GraduationCap,
  CalendarDays,
  AlertTriangle,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import {
  api,
  post,
  setTokens,
  setOrganization,
  signOut,
  download,
} from "./api";
import {
  Brand,
  Empty,
  Field,
  Form,
  Modal,
  Select,
  Table,
  Badge,
  type Row,
} from "./components";
import Setup from "./Setup";
import OfflineCapture, { type OfflineHandle } from "./OfflineCapture";
import ScopeOverview from "./ScopeOverview";
import IndicatorEditor from "./IndicatorEditor";
import Supervision from "./Supervision";
import Intelligence from "./Intelligence";
import ProgrammeEncounter from "./ProgrammeEncounter";
import PlatformAdmin, { MainAdminSetup } from "./PlatformAdmin";
const programmeLabels: Record<string, string> = {
  growth: "Child Growth Monitoring",
  iycf: "IYCF",
  "vitamin-a": "Vitamin A",
  maternal: "Maternal Nutrition",
  gifts: "GIFTS / Adolescent Nutrition",
  rehabilitation: "Nutrition Rehabilitation",
  ncd: "NCD Nutrition",
};
const clinicalRoles = [
  "School Health/GIFTS Officer",
  "District Nutrition Officer",
  "Nutritionist/Dietitian",
  "Midwife/ANC Staff",
  "Community Health Nurse",
  "Field/CHPS Worker",
];
const aggregateRoles = [
  "System Administrator",
  "National Nutrition Administrator",
  "Regional Nutrition Officer",
  "Viewer",
];
const dateToday = () => new Date().toISOString().slice(0, 10);

function Auth({
  onSignIn,
  onSetup,
  onMainSetup,
}: {
  onSignIn: () => void;
  onSetup: () => void;
  onMainSetup?: () => void;
}) {
  const [reset, setReset] = useState(
      new URLSearchParams(location.search).get("reset") || "",
    ),
    [forgot, setForgot] = useState(false),
    [message, setMessage] = useState("");
  return (
    <div className="auth-page">
      <section className="auth-story">
        <Brand />
        <div className="auth-copy">
          <div className="eyebrow light">FROM NUTRITION DATA TO ACTION</div>
          <h1>
            A clearer picture.
            <br />A healthier
            <br />
            <em>tomorrow.</em>
          </h1>
          <p>
            Connect the signals. Coordinate the response.
            <br />
            Bring every nutrition follow-up into focus.
          </p>
          <div className="workflow">
            {["Data", "Signal", "Action", "Follow-up", "Outcome"].map(
              (w, i) => (
                <span key={w}>
                  {w}
                  {i < 4 && <ChevronRight size={14} />}
                </span>
              ),
            )}
          </div>
          <div className="auth-illustration">
            <div className="orbit one" />
            <div className="orbit two" />
            <div className="leaf-medallion">
              <Leaf size={65} />
            </div>
            <span className="orbit-label l1">
              <Activity size={18} />
              See the signal
            </span>
            <span className="orbit-label l2">
              <CheckCircle2 size={18} />
              Close the loop
            </span>
            <span className="orbit-label l3">
              <Users size={18} />
              Reach the community
            </span>
          </div>
        </div>
        <footer>Designed for Ghana. Built around your district.</footer>
      </section>
      <section className="auth-form">
        <div className="auth-form-inner">
          <div className="small-logo">
            <Leaf />
          </div>
          <div className="eyebrow">NUTRITION INTELLIGENCE & FOLLOW-UP</div>
          <h2>
            {reset
              ? "Set a new password"
              : forgot
                ? "Reset your password"
                : "Welcome to NutriTrack"}
          </h2>
          <p className="muted">
            {forgot
              ? "Enter your account email to receive a secure link."
              : "Sign in to your organization workspace."}
          </p>
          <Form
            label={
              reset
                ? "Update password"
                : forgot
                  ? "Send reset link"
                  : "Sign in securely"
            }
            onSubmit={async (d) => {
              if (reset) {
                await post("/api/auth/password-reset/complete", {
                  token: reset,
                  password: d.password,
                });
                setReset("");
                history.replaceState(null, "", "/");
                setMessage("Password updated. Sign in with your new password.");
              } else if (forgot) {
                const r = await post("/api/auth/password-reset/request", {
                  email: d.email,
                });
                setMessage(r.message);
              } else {
                setTokens(await post("/api/auth/login", d));
                onSignIn();
              }
            }}
          >
            {!reset && (
              <Field label="Email address">
                <input
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  placeholder="you@organization.org"
                />
              </Field>
            )}
            {(!forgot || reset) && (
              <Field label={reset ? "New password" : "Password"}>
                <input
                  name="password"
                  type="password"
                  required
                  minLength={reset ? 12 : 1}
                  autoComplete={reset ? "new-password" : "current-password"}
                  placeholder="Enter your password"
                />
              </Field>
            )}
            {message && <div className="notice compact">{message}</div>}
          </Form>
          <button
            className="text-button"
            onClick={() => {
              setForgot(!forgot);
              setMessage("");
            }}
          >
            {forgot ? "Back to sign in" : "Forgot password?"}
          </button>
          <div className="auth-divider" />
          <p className="muted">Setting up a new district?</p>
          <button className="secondary full" onClick={onSetup}>
            Set up your organization
            <ArrowUpRight size={17} />
          </button>
          {onMainSetup && (
            <button className="secondary full" onClick={onMainSetup}>
              Create main administrator account
            </button>
          )}
          <div className="auth-trust">
            <ShieldCheck size={16} />
            Organization-scoped access. No public client registration.
          </div>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const offlineCapture = useRef<OfflineHandle>(null);
  const [config, setConfig] = useState<Row>({ environment: "development" }),
    [me, setMe] = useState<Row | null>(null),
    [setup, setSetup] = useState(false),
    [mainSetup, setMainSetup] = useState(false),
    [organizationView, setOrganizationView] = useState(false),
    [orgId, setOrgId] = useState(""),
    [page, setPage] = useState("Overview"),
    [structure, setStructure] = useState<Row>({
      facilities: [],
      subdistricts: [],
      communities: [],
    }),
    [dash, setDash] = useState<Row | null>(null),
    [records, setRecords] = useState<Row[]>([]),
    [indicators, setIndicators] = useState<Row[]>([]),
    [clients, setClients] = useState<Row[]>([]),
    [registry, setRegistry] = useState<Row[]>([]),
    [aggregate, setAggregate] = useState<Row | null>(null),
    [modal, setModal] = useState(""),
    [selected, setSelected] = useState<Row | null>(null),
    [reportJob, setReportJob] = useState<Row | null>(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [facilityFilters, setFacilityFilters] = useState({
      subdistrict: "",
      type: "",
      status: "",
    }),
    [search, setSearch] = useState(""),
    [mobile, setMobile] = useState(false),
    [online, setOnline] = useState(navigator.onLine),
    [importResult, setImportResult] = useState<Row | null>(null),
    [roleOptions, setRoleOptions] = useState<Row[]>([]);
  const member = me?.memberships.find((m: Row) => m.organization_id === orgId),
    role = member?.role || "",
    isClinical = clinicalRoles.includes(role),
    isAggregate = aggregateRoles.includes(role),
    isAdmin = role === "District Nutrition Officer",
    isSystem = role === "System Administrator";
  const org = member?.organization,
    enabled = org?.configuration?.programmes || [],
    facilityName = (id: string) =>
      structure.facilities.find((f: Row) => f.id === id)?.name ||
      "District-wide",
    subName = (id: string) =>
      structure.subdistricts.find((f: Row) => f.id === id)?.name || "—";
  const notify = (text: string) => {
    setNotice(text);
    setTimeout(() => setNotice(""), 4500);
  };
  const login = async () => {
    try {
      const r = await api<Row>("/api/auth/me");
      setMe(r);
      const id = r.memberships[0]?.organization_id || "";
      setOrganization(id);
      setOrgId(id);
      setSetup(false);
      setMainSetup(false);
      setOrganizationView(false);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  useEffect(() => {
    api<Row[]>("/api/programmes")
      .then((r) => {
        setRegistry(r);
        r.forEach((p) => (programmeLabels[p.code] = p.name));
      })
      .catch(() => {});
    api("/api/public/config")
      .then(setConfig)
      .catch(() =>
        setError("Cannot reach the API. Check the deployment connection."),
      );
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  const load = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    setError("");
    try {
      if (isSystem) {
        setRecords([await api("/api/admin/health")]);
        return;
      }
      const [s, d, i, programmeRegistry] = await Promise.all([
        api<Row>("/api/structure"),
        api<Row>("/api/dashboard"),
        api<Row[]>("/api/indicators"),
        api<Row[]>("/api/programmes"),
      ]);
      setRegistry(programmeRegistry);
      programmeRegistry.forEach((p) => (programmeLabels[p.code] = p.name));
      setStructure(s);
      setDash(d);
      setIndicators(i);
      if (
        [
          "National Nutrition Administrator",
          "Regional Nutrition Officer",
        ].includes(role)
      )
        setAggregate(await api("/api/aggregate/dashboard"));
      else setAggregate(null);
      if (isClinical) {
        setClients(await api<Row[]>("/api/clients"));
      }
      const endpoint: Record<string, string> = {
        Clients: "/api/clients",
        Encounters: "/api/encounters",
        "Action centre": "/api/actions",
        "Monthly reports": "/api/reports",
        "Supportive supervision": "/api/registers/supervision",
        Interventions: "/api/registers/interventions",
        Schools: "/api/registers/schools",
        "Commodity visibility": "/api/registers/commodities",
        "Audit trail": "/api/admin/audit",
        Users: "/api/users",
        "System health": "/api/admin/health",
        ...Object.fromEntries(
          Object.values(programmeLabels).map((v) => [v, "/api/encounters"]),
        ),
      };
      if (endpoint[page]) {
        const r = await api(endpoint[page]);
        setRecords(Array.isArray(r) ? r : [r]);
      } else setRecords([]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [orgId, page, isClinical, isSystem]);
  useEffect(() => {
    load();
  }, [load]);
  const navigate = (p: string) => {
    setPage(p);
    setSearch("");
    setMobile(false);
    setSelected(null);
  };
  const save = async (path: string, data: Row, method = "POST") => {
    await post(path, data, method);
    setModal("");
    setSelected(null);
    notify("Record saved successfully");
    await load();
  };
  const filtered = records.filter((r) =>
    JSON.stringify(r).toLowerCase().includes(search.toLowerCase()),
  );
  const programme = Object.keys(programmeLabels).find(
      (k) => programmeLabels[k] === page,
    ),
    clinicalPage = page === "Encounters" || !!programme;
  const pageSubtitles: Record<string, string> = {
    Overview: "Your nutrition situation, connected to the next action.",
    "Action centre":
      "Assign responsibility. Follow through. Record the outcome.",
    Facilities: "A connected view of your local health structure.",
    Clients: "Authorized client records and nutrition service history.",
    "Monthly reports": "From facility submission to verified, approved data.",
    "Community map":
      "See where nutrition services and priorities come together.",
    Indicators: "Locally approved definitions, targets and measurement.",
    "Supportive supervision":
      "Turn supervision findings into accountable corrective actions.",
    Interventions: "Connect programme activities with subsequent trends.",
    "Commodity visibility":
      "Understand availability alongside nutrition service gaps.",
    Schools: "Your adolescent nutrition programme school registry.",
    "Audit trail": "A traceable record of changes across your organization.",
    "System health": "Application and data platform status.",
    "Master data": "Configure the structure that supports your programmes.",
    Users: "Least-privilege access for your district team.",
    Settings: "Your organization identity and programme configuration.",
  };
  if (mainSetup)
    return (
      <MainAdminSetup onComplete={login} onBack={() => setMainSetup(false)} />
    );
  if (setup) return <Setup onComplete={login} onBack={() => setSetup(false)} />;
  if (!me)
    return (
      <>
        {config.environment !== "production" && (
          <div className="environment-banner">
            {config.environment.toUpperCase()} ENVIRONMENT · Use fictional data
            only
          </div>
        )}
        {error && <div className="global-error">{error}</div>}
        <Auth
          onSignIn={login}
          onSetup={() => setSetup(true)}
          onMainSetup={
            config.main_admin_setup_available
              ? () => setMainSetup(true)
              : undefined
          }
        />
      </>
    );
  if (me.platform_admin && !organizationView)
    return (
      <PlatformAdmin
        environment={config.environment}
        onSignOut={async () => {
          await signOut();
          setMe(null);
          setOrgId("");
          api("/api/public/config").then(setConfig);
        }}
        onOpenOrganization={async (id) => {
          setMe(await api("/api/auth/me"));
          setOrganization(id);
          setOrgId(id);
          setDash(null);
          setPage("Overview");
          setOrganizationView(true);
        }}
      />
    );
  const higherScope = me.grants?.some((g: Row) =>
    ["NATIONAL", "REGION"].includes(g.level),
  );
  if (!me.platform_admin && higherScope && !organizationView)
    return (
      <ScopeOverview
        me={me}
        environment={config.environment}
        onSignOut={async () => {
          await signOut();
          setMe(null);
        }}
        onOpenOrganization={(id) => {
          setOrganization(id);
          setOrgId(id);
          setPage("Overview");
          setOrganizationView(true);
        }}
      />
    );
  if (!orgId)
    return (
      <div className="setup-page">
        <main>
          <Brand />
          <h1>No active organization assignment</h1>
          <p>
            Your account has no current organization access. Ask your
            administrator to assign your duties and location.
          </p>
          <button
            onClick={async () => {
              await signOut();
              setMe(null);
            }}
          >
            Sign out
          </button>
        </main>
      </div>
    );
  const nav = [
    {
      label: "WORKSPACE",
      items: isSystem
        ? [["System health", ShieldCheck]]
        : [
            ["Overview", LayoutDashboard],
            ...(!isAggregate ? [["Action centre", Target]] : []),
            ["Facilities", Building2],
            ["Community map", MapPin],
          ],
    },
    {
      label: "NUTRITION PROGRAMMES",
      items: isClinical
        ? enabled
            .filter(
              (k: string) => role !== "Midwife/ANC Staff" || k === "maternal",
            )
            .map((k: string) => [programmeLabels[k] || k, HeartPulse])
        : [],
    },
    {
      label: "OPERATIONS",
      items: isSystem
        ? []
        : [
            ...(isClinical
              ? [
                  ["Clients", Users],
                  ["Encounters", ClipboardList],
                ]
              : []),
            ["Monthly reports", FileText],
            ...(!isAggregate
              ? [
                  ["Supportive supervision", ClipboardCheck],
                  ["Interventions", CalendarDays],
                  ...(enabled.includes("gifts")
                    ? [["Schools", GraduationCap]]
                    : []),
                  ["Commodity visibility", Package],
                ]
              : []),
          ],
    },
    {
      label: "ADMINISTRATION",
      items: isAdmin
        ? [
            ["Master data", Settings],
            ["Indicators", BarChart3],
            ["Users", Users],
            ["Audit trail", ShieldCheck],
            ["System health", Activity],
            ["Settings", Settings],
          ]
        : [],
    },
  ];
  const title = programme ? page : page;
  const addLabels: Record<string, string> = {
    Clients: "Register client",
    Encounters: "Record encounter",
    "Action centre": "Create action",
    Facilities: "Add facility",
    "Monthly reports": "New monthly report",
    Indicators: "Add indicator",
    "Supportive supervision": "Record visit",
    Interventions: "Add intervention",
    Schools: "Add school",
    "Commodity visibility": "Add stock record",
    Users: "Add user",
  };
  const canAdd =
    !isAggregate &&
    page !== "Supportive supervision" &&
    (isAdmin || !["Facilities", "Indicators", "Users"].includes(page)) &&
    (!!addLabels[page] || clinicalPage);
  return (
    <div className="app-shell">
      {config.environment !== "production" && (
        <div className="environment-banner">
          {config.environment.toUpperCase()} ENVIRONMENT · Use fictional data
          only
        </div>
      )}
      {!online && (
        <div className="offline-banner">
          <WifiOff size={16} />
          You are offline. Reconnect to view or save health records.
        </div>
      )}
      <aside className={`sidebar ${mobile ? "visible" : ""}`}>
        <div className="sidebar-brand">
          <Brand />
          <button
            className="icon-button mobile-only"
            onClick={() => setMobile(false)}
          >
            <X />
          </button>
        </div>
        {me.platform_admin && (
          <button
            className="secondary"
            onClick={() => setOrganizationView(false)}
          >
            National administration
          </button>
        )}
        {!me.platform_admin && higherScope && (
          <button
            className="secondary"
            onClick={() => setOrganizationView(false)}
          >
            Regional / national overview
          </button>
        )}
        <div className="workspace-switch">
          <small>ORGANIZATION WORKSPACE</small>
          <select
            aria-label="Switch organization"
            value={orgId}
            onChange={(e) => {
              setOrganization(e.target.value);
              setOrgId(e.target.value);
              setDash(null);
              setClients([]);
              navigate("Overview");
            }}
          >
            {me.memberships.map((m: Row) => (
              <option key={m.organization_id} value={m.organization_id}>
                {m.organization.name}
              </option>
            ))}
          </select>
          <span>
            <span className="live-dot" />
            {(member?.access_level || "HEALTH_DISTRICT")
              .replaceAll("_", " ")
              .toLowerCase()}{" "}
            access
          </span>
        </div>
        <nav>
          {nav.map(
            (group) =>
              group.items.length > 0 && (
                <div className="nav-group" key={group.label}>
                  <small>{group.label}</small>
                  {group.items.map(([label, Icon]: any) => (
                    <button
                      key={label}
                      className={page === label ? "active" : ""}
                      onClick={() => navigate(label)}
                    >
                      <Icon size={18} />
                      <span>{label}</span>
                      {page === label && <span className="nav-dot" />}
                    </button>
                  ))}
                </div>
              ),
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="product-note">
            <Leaf size={19} />
            <span>
              From nutrition data
              <br />
              <strong>to meaningful action.</strong>
            </span>
          </div>
          <button
            className="user-profile"
            onClick={async () => {
              await signOut();
              setMe(null);
              setDash(null);
              setOrgId("");
              setClients([]);
              setRecords([]);
            }}
          >
            <div className="avatar">
              {me.user.name
                .split(" ")
                .map((n: string) => n[0])
                .slice(0, 2)
                .join("")}
            </div>
            <span>
              <strong>{me.user.name}</strong>
              <small>{role}</small>
            </span>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-button mobile-only"
              onClick={() => setMobile(true)}
            >
              <Menu />
            </button>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{title}</strong>
          </div>
          <div className="topbar-right">
            <span className="today">
              <CalendarDays size={15} />
              {new Date().toLocaleDateString("en-GB", {
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </span>
            <button
              className="icon-button"
              onClick={() => {
                navigate("Action centre");
              }}
              aria-label="Open action alerts"
            >
              <Bell size={20} />
              {dash?.overdue_actions > 0 && (
                <span className="notification-dot" />
              )}
            </button>
            <div className="avatar small">{me.user.name[0]}</div>
          </div>
        </header>
        <main className="main-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">{org?.name}</div>
              <h1>
                {title === "Overview" ? "Nutrition situation overview" : title}
              </h1>
              <p>
                {pageSubtitles[page] ||
                  "Record services, identify follow-up needs and track outcomes."}
              </p>
            </div>
            <div className="page-actions">
              <button className="secondary" onClick={load} disabled={loading}>
                <RefreshCw size={15} className={loading ? "spin" : ""} />
                <span>Refresh</span>
              </button>
              {canAdd && (
                <button
                  className="primary"
                  onClick={() => setModal(clinicalPage ? "Encounters" : page)}
                >
                  <Plus size={17} />
                  {addLabels[page] || "Record encounter"}
                </button>
              )}
            </div>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          {notice && (
            <div className="toast" role="status">
              <CheckCircle2 size={18} />
              {notice}
            </div>
          )}
          {page === "Overview" && aggregate && (
            <section className="panel" style={{ marginBottom: 22 }}>
              <div className="panel-heading">
                <div>
                  <h3>
                    {role === "National Nutrition Administrator"
                      ? "National"
                      : "Regional"}{" "}
                    authorized district overview
                  </h3>
                  <p>
                    {aggregate.scope} · {aggregate.regions} regions ·{" "}
                    {aggregate.districts} districts
                  </p>
                </div>
              </div>
              <Table
                rows={aggregate.organizations.map((r: Row) => ({
                  ...r,
                  id: r.organization_id,
                }))}
                columns={[
                  { key: "organization_name", label: "District workspace" },
                  { key: "region", label: "Region" },
                  { key: "facilities", label: "Facilities" },
                  { key: "approved_reports", label: "Approved reports" },
                ]}
              />
              <p className="muted padded">{aggregate.note}</p>
            </section>
          )}
          {page === "Overview" && dash && (
            <>
              <section className="overview-hero">
                <div>
                  <span className="hero-pill">
                    <span className="live-dot" />
                    DISTRICT INTELLIGENCE
                  </span>
                  <h2>
                    Every signal deserves
                    <br />a coordinated response.
                  </h2>
                  <p>
                    Monitor your programmes. Focus your team.
                    <br />
                    Follow every action through to its outcome.
                  </p>
                  <button
                    onClick={() =>
                      navigate(
                        isAggregate ? "Monthly reports" : "Action centre",
                      )
                    }
                  >
                    Review {isAggregate ? "reports" : "the action centre"}
                    <ArrowRight size={17} />
                  </button>
                </div>
                <div className="hero-graphic">
                  <div className="hero-circle">
                    <Leaf size={50} />
                  </div>
                  <span className="graphic-tag top">
                    <Activity size={16} />
                    DATA TO SIGNAL
                  </span>
                  <span className="graphic-tag bottom">
                    <CheckCircle2 size={16} />
                    ACTION TO OUTCOME
                  </span>
                  <div className="graphic-line" />
                </div>
              </section>
              <div className="stats-grid">
                {[
                  [
                    Building2,
                    "Active health facilities",
                    dash.facilities,
                    "Connected to this workspace",
                  ],
                  [
                    FileText,
                    "Approved monthly reports",
                    dash.approved_reports,
                    "Verified programme evidence",
                  ],
                  [
                    Target,
                    "Actions requiring attention",
                    dash.open_actions,
                    `${dash.overdue_actions} overdue actions`,
                  ],
                  [
                    CheckCircle2,
                    "Completed actions",
                    dash.completed_actions,
                    "Outcomes recorded",
                  ],
                ].map(([Icon, label, value, hint]: any) => (
                  <div className="stat-card" key={label}>
                    <div className="stat-top">
                      <span>{label}</span>
                      <Icon size={19} />
                    </div>
                    <strong>{value}</strong>
                    <small
                      className={
                        String(hint).includes("overdue") && dash.overdue_actions
                          ? "danger"
                          : ""
                      }
                    >
                      {hint}
                    </small>
                  </div>
                ))}
              </div>
              <div className="dashboard-grid">
                <section className="panel trend-panel">
                  <div className="panel-heading">
                    <div>
                      <h3>Nutrition indicator trends</h3>
                      <p>Approved and locked reports · pooled coverage</p>
                    </div>
                    <span className="mini-label">%</span>
                  </div>
                  {dash.trends.length ? (
                    <ResponsiveContainer width="100%" height={280}>
                      <LineChart data={dash.trends}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="period" tickLine={false} />
                        <YAxis domain={[0, 100]} tickLine={false} />
                        <Tooltip />
                        <Legend />
                        {dash.indicators.map((i: Row, index: number) => (
                          <Line
                            key={i.id}
                            dataKey={i.name}
                            type="monotone"
                            stroke={
                              ["#1d7053", "#daa94b", "#647cad", "#b66e55"][
                                index % 4
                              ]
                            }
                            strokeWidth={2.5}
                            connectNulls={false}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <Empty
                      title="Build your first indicator trend"
                      text="Configure approved indicators, then submit and approve facility reports. Trends will appear here."
                      action={
                        isAdmin && (
                          <button
                            className="text-button"
                            onClick={() => navigate("Indicators")}
                          >
                            Configure indicators
                            <ArrowRight size={15} />
                          </button>
                        )
                      }
                    />
                  )}
                </section>
                <section className="panel signal-panel">
                  <div className="panel-heading">
                    <div>
                      <h3>Signals needing attention</h3>
                      <p>Compare results with approved targets</p>
                    </div>
                    <span className="count-pill">{dash.signals.length}</span>
                  </div>
                  {dash.signals.length ? (
                    dash.signals.map((s: Row, i: number) => (
                      <div className="signal" key={i}>
                        <span className="signal-icon">
                          <AlertTriangle size={17} />
                        </span>
                        <div>
                          <strong>{s.title}</strong>
                          <p>{s.problem}</p>
                          {!isAggregate && (
                            <button
                              className="text-button"
                              onClick={() => {
                                setSelected(s);
                                setModal("Action centre");
                              }}
                            >
                              Create an action
                              <ArrowUpRight size={14} />
                            </button>
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <Empty
                      title="No target exceptions yet"
                      text="Signals appear when approved indicator results fall outside configured targets."
                    />
                  )}
                </section>
              </div>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h3>Facility performance</h3>
                    <p>Reporting, follow-up and transparent data quality</p>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => navigate("Facilities")}
                  >
                    All facilities
                    <ArrowRight size={15} />
                  </button>
                </div>
                {dash.facility_profiles.length ? (
                  <Table
                    rows={dash.facility_profiles}
                    onSelect={(r) => {
                      setSelected(r);
                      setModal("Facility profile");
                    }}
                    columns={[
                      { key: "name", label: "Health facility" },
                      { key: "last_report", label: "Latest report" },
                      {
                        key: "report_state",
                        label: "Report status",
                        render: (r) =>
                          r.report_state ? (
                            <Badge>{r.report_state}</Badge>
                          ) : (
                            "No report"
                          ),
                      },
                      {
                        key: "data_quality",
                        label: "Data quality",
                        render: (r) =>
                          r.data_quality === null ? (
                            "Not measured"
                          ) : (
                            <div className="quality">
                              <span>{r.data_quality}%</span>
                              <div>
                                <i style={{ width: `${r.data_quality}%` }} />
                              </div>
                            </div>
                          ),
                      },
                      { key: "open_actions", label: "Open actions" },
                    ]}
                  />
                ) : (
                  <Empty
                    title="Connect your health facilities"
                    text="Add facilities under your health sub-districts to begin district operations."
                    action={
                      isAdmin && (
                        <button
                          className="secondary"
                          onClick={() => navigate("Facilities")}
                        >
                          Add facilities
                          <Plus size={15} />
                        </button>
                      )
                    }
                  />
                )}
              </section>
              <p className="methodology">
                <ShieldCheck size={14} />
                {dash.methodology}
              </p>
            </>
          )}
          {page === "Facilities" && (
            <section className="panel">
              <div className="panel-toolbar">
                <div className="search-input">
                  <Search size={16} />
                  <input
                    placeholder="Search facilities, codes or communities…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <div>
                  {isAdmin && (
                    <button
                      className="secondary"
                      onClick={() => {
                        setImportResult(null);
                        setModal("Bulk import");
                      }}
                    >
                      <Plus size={15} />
                      Bulk import
                    </button>
                  )}
                  <button
                    className="secondary"
                    onClick={() =>
                      download(
                        "/api/facilities/export",
                        "facilities.csv",
                      ).catch((e) => setError(e.message))
                    }
                  >
                    <Download size={15} />
                    Export
                  </button>
                </div>
              </div>
              <div className="facility-filters">
                <select
                  aria-label="Filter by sub-district"
                  value={facilityFilters.subdistrict}
                  onChange={(e) =>
                    setFacilityFilters({
                      ...facilityFilters,
                      subdistrict: e.target.value,
                    })
                  }
                >
                  <option value="">All sub-districts</option>
                  {structure.subdistricts.map((s: Row) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Filter by facility type"
                  value={facilityFilters.type}
                  onChange={(e) =>
                    setFacilityFilters({
                      ...facilityFilters,
                      type: e.target.value,
                    })
                  }
                >
                  <option value="">All facility types</option>
                  {org.configuration.facility_types.map((t: string) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
                <select
                  aria-label="Filter by facility status"
                  value={facilityFilters.status}
                  onChange={(e) =>
                    setFacilityFilters({
                      ...facilityFilters,
                      status: e.target.value,
                    })
                  }
                >
                  <option value="">All statuses</option>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </div>
              {structure.facilities.length ? (
                <Table
                  rows={structure.facilities.filter(
                    (f: Row) =>
                      JSON.stringify(f)
                        .toLowerCase()
                        .includes(search.toLowerCase()) &&
                      (!facilityFilters.subdistrict ||
                        f.subdistrict_id === facilityFilters.subdistrict) &&
                      (!facilityFilters.type ||
                        f.facility_type === facilityFilters.type) &&
                      (!facilityFilters.status ||
                        String(f.active) === facilityFilters.status),
                  )}
                  columns={[
                    {
                      key: "name",
                      label: "Facility",
                      render: (r) => (
                        <button
                          className="table-link"
                          onClick={() => {
                            setSelected(r);
                            setModal("Facility profile");
                          }}
                        >
                          {r.name}
                          <ArrowUpRight size={13} />
                        </button>
                      ),
                    },
                    { key: "code", label: "Code" },
                    { key: "facility_type", label: "Type" },
                    {
                      key: "subdistrict_id",
                      label: "Sub-district",
                      render: (r) => subName(r.subdistrict_id),
                    },
                    { key: "community", label: "Community" },
                    {
                      key: "active",
                      label: "Status",
                      render: (r) => (
                        <Badge>{r.active ? "Active" : "Inactive"}</Badge>
                      ),
                    },
                    {
                      key: "edit",
                      label: "Manage",
                      render: (r) =>
                        isAdmin && (
                          <button
                            className="text-button"
                            onClick={() => {
                              setSelected(r);
                              setModal("Facilities");
                            }}
                          >
                            Edit
                          </button>
                        ),
                    },
                  ]}
                />
              ) : (
                <Empty
                  title="Your facility directory starts here"
                  text="Add a health facility or import a validated CSV/XLSX directory."
                />
              )}
            </section>
          )}
          {page === "Community map" && (
            <section className="panel map-panel">
              <div className="panel-heading">
                <div>
                  <h3>Health facility coverage</h3>
                  <p>
                    Only recorded facility coordinates are shown. Client
                    locations are never plotted.
                  </p>
                </div>
              </div>
              <MapContainer
                center={[7.9, -1.1]}
                zoom={7}
                style={{ height: 480, width: "100%" }}
              >
                <TileLayer
                  attribution="&copy; OpenStreetMap contributors"
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {structure.facilities
                  .filter((f: Row) => f.latitude != null && f.longitude != null)
                  .map((f: Row) => (
                    <CircleMarker
                      key={f.id}
                      center={[f.latitude, f.longitude]}
                      radius={8}
                      pathOptions={{ color: "#1d7053", fillOpacity: 0.8 }}
                    >
                      <Popup>
                        <strong>{f.name}</strong>
                        <br />
                        {f.facility_type}
                        <br />
                        {subName(f.subdistrict_id)}
                      </Popup>
                    </CircleMarker>
                  ))}
              </MapContainer>
              {!structure.facilities.some((f: Row) => f.latitude != null) && (
                <p className="muted padded">
                  No facility coordinates have been recorded. Add authorized
                  coordinates in facility management.
                </p>
              )}
            </section>
          )}
          {page === "Clients" && (
            <section className="panel">
              <div className="panel-toolbar">
                <div className="search-input">
                  <Search size={16} />
                  <input
                    placeholder="Search authorized clients…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <span className="privacy-note">
                  <ShieldCheck size={14} />
                  Confidential · access audited
                </span>
              </div>
              {filtered.length ? (
                <Table
                  rows={filtered}
                  onSelect={(r) => {
                    setSelected(r);
                    setModal("Client history");
                  }}
                  columns={[
                    { key: "name", label: "Client" },
                    { key: "reference", label: "Reference" },
                    { key: "date_of_birth", label: "Date of birth" },
                    { key: "sex", label: "Sex" },
                    {
                      key: "facility_id",
                      label: "Facility",
                      render: (r) => facilityName(r.facility_id),
                    },
                  ]}
                />
              ) : (
                <Empty
                  title="No client records found"
                  text="Register a client to record nutrition services and coordinate their follow-up."
                />
              )}
            </section>
          )}
          {clinicalPage && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h3>
                    {programme
                      ? "Programme service register"
                      : "Nutrition encounters"}
                  </h3>
                  <p>
                    Clinical assessments are recorded by authorized staff. The
                    system does not diagnose.
                  </p>
                </div>
              </div>
              {records.filter((r) => !programme || r.programme === programme)
                .length ? (
                <Table
                  rows={records.filter(
                    (r) => !programme || r.programme === programme,
                  )}
                  columns={[
                    { key: "visit_date", label: "Visit" },
                    {
                      key: "client_id",
                      label: "Client",
                      render: (r) =>
                        clients.find((c) => c.id === r.client_id)?.name ||
                        "Authorized client",
                    },
                    {
                      key: "programme",
                      label: "Programme",
                      render: (r) =>
                        programmeLabels[r.programme] || r.programme,
                    },
                    {
                      key: "risk",
                      label: "Assessment priority",
                      render: (r) => <Badge>{r.risk}</Badge>,
                    },
                    { key: "followup_date", label: "Next follow-up" },
                    { key: "assessment", label: "Assessment" },
                  ]}
                />
              ) : (
                <Empty
                  title="Ready for your next service encounter"
                  text="Record an assessment and follow-up date. A follow-up action is created automatically when needed."
                />
              )}
            </section>
          )}
          {page === "Action centre" && (
            <>
              <div className="action-summary">
                <div>
                  <span className="live-dot" />
                  <strong>
                    {records.filter((r) => r.status === "Open").length}
                  </strong>{" "}
                  open
                </div>
                <div>
                  <AlertTriangle size={17} />
                  <strong>
                    {
                      records.filter(
                        (r) =>
                          r.due_date < dateToday() &&
                          ["Open", "In progress"].includes(r.status),
                      ).length
                    }
                  </strong>{" "}
                  overdue
                </div>
                <div>
                  <CheckCircle2 size={17} />
                  <strong>
                    {records.filter((r) => r.status === "Completed").length}
                  </strong>{" "}
                  completed
                </div>
              </div>
              <section className="panel">
                <div className="panel-toolbar">
                  <div className="search-input">
                    <Search size={16} />
                    <input
                      placeholder="Search actions…"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </div>
                  <small>DATA → SIGNAL → ACTION → FOLLOW-UP → OUTCOME</small>
                </div>
                {filtered.length ? (
                  <Table
                    rows={filtered}
                    onSelect={(r) => {
                      setSelected(r);
                      setModal("Update action");
                    }}
                    columns={[
                      { key: "title", label: "Action" },
                      {
                        key: "facility_id",
                        label: "Facility",
                        render: (r) => facilityName(r.facility_id),
                      },
                      {
                        key: "priority",
                        label: "Priority",
                        render: (r) => <Badge>{r.priority}</Badge>,
                      },
                      { key: "due_date", label: "Due date" },
                      {
                        key: "status",
                        label: "Status",
                        render: (r) => <Badge>{r.status}</Badge>,
                      },
                    ]}
                  />
                ) : (
                  <Empty
                    title="Give your next action a clear owner"
                    text="Create an action from an indicator signal, supervision finding or nutrition encounter."
                  />
                )}
              </section>
            </>
          )}
          {isClinical && (
            <OfflineCapture
              key={`${me.user.id}:${orgId}`}
              ref={offlineCapture}
              userId={me.user.id}
              organizationId={orgId}
              onSynced={load}
            />
          )}
          {page === "Overview" && !isSystem && (
            <Intelligence organizationId={orgId} canAct={isAdmin} />
          )}
          {page === "Monthly reports" && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h3>Monthly reporting workflow</h3>
                  <p>Draft → Submitted → Verified → Approved → Locked</p>
                </div>
              </div>
              {records.length ? (
                <Table
                  rows={records}
                  onSelect={(r) => {
                    setSelected(r);
                    setModal("Report review");
                  }}
                  columns={[
                    { key: "period", label: "Period" },
                    {
                      key: "facility_id",
                      label: "Facility",
                      render: (r) => facilityName(r.facility_id),
                    },
                    {
                      key: "state",
                      label: "State",
                      render: (r) => <Badge>{r.state}</Badge>,
                    },
                    { key: "revision", label: "Revision" },
                    {
                      key: "updated_at",
                      label: "Last updated",
                      render: (r) =>
                        new Date(r.updated_at).toLocaleDateString(),
                    },
                  ]}
                />
              ) : (
                <Empty
                  title="Build your first reporting period"
                  text="Enter facility numerators and denominators using your organization's approved indicator definitions."
                />
              )}
            </section>
          )}
          {page === "Indicators" && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h3>Approved indicator registry</h3>
                  <p>
                    Definitions and targets are configured by your district
                    administrator.
                  </p>
                </div>
              </div>
              {indicators.length ? (
                <Table
                  rows={indicators}
                  columns={[
                    { key: "name", label: "Indicator" },
                    {
                      key: "programme",
                      label: "Programme",
                      render: (r) => programmeLabels[r.programme],
                    },
                    {
                      key: "target",
                      label: "Target",
                      render: (r) =>
                        `${r.direction === "higher" ? "≥" : "≤"} ${r.target}%`,
                    },
                    { key: "denominator_definition", label: "Denominator" },
                    { key: "approval_reference", label: "Approval reference" },
                  ]}
                />
              ) : (
                <Empty
                  title="Define what progress looks like"
                  text="Add locally approved indicators with explicit numerators, denominators and targets."
                />
              )}
            </section>
          )}
          {page === "Supportive supervision" && (
            <Supervision
              facilities={structure.facilities}
              checklist={org.configuration.supervision_checklist || []}
              canManage={isAdmin}
            />
          )}
          {["Interventions", "Schools", "Commodity visibility"].includes(
            page,
          ) && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h3>{page} register</h3>
                  <p>
                    {page === "Interventions"
                      ? "Record reach and outcomes. Trend changes do not establish causality."
                      : "Structured programme records with source and entry history."}
                  </p>
                </div>
              </div>
              {records.length ? (
                <Table
                  rows={records}
                  onSelect={(r) => {
                    setSelected(r);
                    setModal("Register details");
                  }}
                  columns={[
                    {
                      key: "title",
                      label:
                        page === "Schools"
                          ? "School"
                          : page === "Commodity visibility"
                            ? "Item"
                            : "Activity",
                    },
                    {
                      key: "facility_id",
                      label: "Facility",
                      render: (r) => facilityName(r.facility_id),
                    },
                    {
                      key: "details",
                      label:
                        page === "Commodity visibility"
                          ? "Closing balance"
                          : "Date / period",
                      render: (r) =>
                        page === "Commodity visibility"
                          ? r.details.closing
                          : r.details.date || r.details.period || "—",
                    },
                    {
                      key: "created_at",
                      label: "Entered",
                      render: (r) =>
                        new Date(r.created_at).toLocaleDateString(),
                    },
                  ]}
                />
              ) : (
                <Empty
                  title={`Your ${page.toLowerCase()} register is ready`}
                  text="Create your first record to build a connected programme history."
                />
              )}
            </section>
          )}
          {page === "Master data" && (
            <>
              <div className="master-grid">
                {[
                  [
                    "Health sub-districts",
                    structure.subdistricts,
                    "Sub-district",
                  ],
                  [
                    "Communities / CHPS zones",
                    structure.communities,
                    "Community",
                  ],
                  ["Facilities", structure.facilities, "Facilities"],
                  ["Schools", [], "Schools"],
                ].map(([label, rows, modalName]: any) => (
                  <section className="panel" key={label}>
                    <div className="panel-heading">
                      <div>
                        <h3>{label}</h3>
                        <p>{rows.length} local records</p>
                      </div>
                      <button
                        className="icon-button"
                        aria-label={`Add ${label}`}
                        onClick={() =>
                          modalName === "Facilities" || modalName === "Schools"
                            ? navigate(modalName)
                            : setModal(modalName)
                        }
                      >
                        <Plus size={19} />
                      </button>
                    </div>
                    {rows.length ? (
                      <ul className="master-list">
                        {rows.map((r: Row) => (
                          <li key={r.id}>
                            <span>{r.name}</span>
                            <Badge>{r.active ? "Active" : "Inactive"}</Badge>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted padded">No records added yet.</p>
                    )}
                  </section>
                ))}
              </div>
              <div className="notice">
                <ShieldCheck />
                <div>
                  <h3>National geography is versioned master data</h3>
                  <p>
                    The 16 regions are loaded from government master data.
                    Health districts, sub-districts and facilities are managed
                    by authorized health directorates.
                  </p>
                </div>
              </div>
            </>
          )}
          {page === "Users" && (
            <section className="panel">
              {records.length ? (
                <Table
                  rows={records}
                  columns={[
                    { key: "name", label: "Name" },
                    { key: "email", label: "Email" },
                    { key: "role", label: "Role" },
                    {
                      key: "facility_id",
                      label: "Facility scope",
                      render: (r) => facilityName(r.facility_id),
                    },
                  ]}
                />
              ) : (
                <Empty />
              )}
            </section>
          )}
          {page === "Audit trail" && (
            <section className="panel">
              <Table
                rows={records}
                columns={[
                  {
                    key: "created_at",
                    label: "Time",
                    render: (r) => new Date(r.created_at).toLocaleString(),
                  },
                  { key: "event", label: "Event" },
                  { key: "entity_id", label: "Entity" },
                  {
                    key: "details",
                    label: "Details",
                    render: (r) => <code>{JSON.stringify(r.details)}</code>,
                  },
                ]}
              />
            </section>
          )}
          {(page === "System health" || isSystem) && records[0] && (
            <>
              <div className="health-grid">
                {Object.entries(records[0]).map(([key, value]) => (
                  <section className="panel health-card" key={key}>
                    <small>{key.replaceAll("_", " ")}</small>
                    <strong>
                      {value === null ? "Not verified" : String(value)}
                    </strong>
                  </section>
                ))}
              </div>
              <div className="notice">
                <ShieldCheck />
                <p>
                  Backup protection is unverified until a restore exercise is
                  completed. Clinical offline synchronization and background
                  queues are not enabled in this release.
                </p>
              </div>
            </>
          )}
          {page === "Settings" && org && (
            <section className="panel settings-panel">
              <h3>Organization identity & programme configuration</h3>
              <Form
                label="Save configuration"
                onSubmit={async (d) => {
                  const {
                    w_completeness,
                    w_timeliness,
                    w_validity,
                    ...values
                  } = d;
                  await save(
                    "/api/configuration",
                    {
                      ...values,
                      quality_weights: {
                        Completeness: Number(w_completeness),
                        Timeliness: Number(w_timeliness),
                        Validity: Number(w_validity),
                      },
                      report_deadline_day: Number(d.report_deadline_day),
                      deterioration_threshold_pp: Number(
                        d.deterioration_threshold_pp,
                      ),
                      supervision_checklist: d.supervision_checklist
                        .split("\n")
                        .map((v: string) => v.trim())
                        .filter(Boolean),
                      facility_types: String(d.facility_types)
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                      programmes: enabled,
                    },
                    "PUT",
                  );
                  await login();
                }}
              >
                <div className="form-grid">
                  <Field label="Deterioration signal threshold (percentage points)">
                    <input
                      name="deterioration_threshold_pp"
                      type="number"
                      min="0.1"
                      max="100"
                      step="0.1"
                      defaultValue={
                        org.configuration.deterioration_threshold_pp || 5
                      }
                    />
                  </Field>
                  <Field label="Supervision checklist (one question per line)">
                    <textarea
                      name="supervision_checklist"
                      rows={5}
                      defaultValue={(
                        org.configuration.supervision_checklist || []
                      ).join("\n")}
                    />
                  </Field>
                  <Field label="Report header">
                    <input
                      name="report_header"
                      defaultValue={org.configuration.report_header || org.name}
                      required
                    />
                  </Field>
                  <Field label="Contact details">
                    <input
                      name="contact"
                      defaultValue={org.configuration.contact || ""}
                    />
                  </Field>
                  <Field label="Reporting officer">
                    <input
                      name="reporting_officer"
                      defaultValue={org.configuration.reporting_officer || ""}
                    />
                  </Field>
                  <Field label="Authorized logo URL">
                    <input
                      name="logo_url"
                      type="url"
                      defaultValue={org.configuration.logo_url || ""}
                    />
                  </Field>
                  <Field
                    label="Facility types"
                    hint="Comma-separated. Keep existing types to preserve facility compatibility."
                  >
                    <input
                      name="facility_types"
                      defaultValue={org.configuration.facility_types.join(", ")}
                      required
                    />
                  </Field>
                  {[
                    ["Completeness", "w_completeness"],
                    ["Timeliness", "w_timeliness"],
                    ["Validity", "w_validity"],
                  ].map(([key, name]) => (
                    <Field key={name} label={`${key} quality weight`}>
                      <input
                        name={name}
                        type="number"
                        min="0"
                        max="100"
                        step="0.1"
                        required
                        defaultValue={
                          org.configuration.quality_weights?.[key] ?? 1
                        }
                      />
                    </Field>
                  ))}
                  <Field label="Report submission deadline (day of next month)">
                    <input
                      name="report_deadline_day"
                      type="number"
                      min="1"
                      max="28"
                      defaultValue={org.configuration.report_deadline_day ?? 5}
                    />
                  </Field>
                </div>
                <p className="muted">
                  Enabled programmes:{" "}
                  {enabled
                    .map((k: string) => programmeLabels[k] || k)
                    .join(", ")}
                </p>
              </Form>
              <button
                className="text-button"
                onClick={() => setModal("Programme configuration")}
              >
                Change enabled programmes
                <ArrowRight size={15} />
              </button>
            </section>
          )}
          <footer className="main-footer">
            <span>
              NutriTrack Ghana <b>v{config.version || "0.1.0"}</b>
            </span>
            <span>From Nutrition Data to Action.</span>
            <button
              className="text-button"
              onClick={async () => {
                setSelected((await api<Row[]>("/api/changelog"))[0]);
                setModal("What’s new");
              }}
            >
              What’s new
              <ArrowUpRight size={12} />
            </button>
          </footer>
        </main>
      </div>
      {modal && (
        <Modal
          title={modal}
          onClose={() => {
            setModal("");
            setSelected(null);
          }}
        >
          {modal === "Facilities" && (
            <Form
              onSubmit={async (d) =>
                save(
                  selected
                    ? `/api/facilities/${selected.id}`
                    : "/api/facilities",
                  {
                    ...d,
                    email: d.email || null,
                    latitude: d.latitude ? Number(d.latitude) : null,
                    longitude: d.longitude ? Number(d.longitude) : null,
                    active: d.active === "true",
                    programmes: selected?.programmes || [],
                  },
                  selected ? "PUT" : "POST",
                )
              }
            >
              <div className="form-grid">
                <Field label="Facility name">
                  <input name="name" required defaultValue={selected?.name} />
                </Field>
                <Field label="Code">
                  <input name="code" defaultValue={selected?.code} />
                </Field>
                <Field label="Facility type">
                  <select
                    name="facility_type"
                    defaultValue={selected?.facility_type}
                  >
                    {org.configuration.facility_types.map((v: string) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Health sub-district">
                  <Select
                    name="subdistrict_id"
                    options={structure.subdistricts}
                    value={selected?.subdistrict_id}
                    onChange={(v) =>
                      selected &&
                      setSelected({ ...selected, subdistrict_id: v })
                    }
                  />
                </Field>
                <Field label="Community">
                  <input name="community" defaultValue={selected?.community} />
                </Field>
                <Field label="Ownership">
                  <select
                    name="ownership"
                    defaultValue={selected?.ownership || "Public"}
                  >
                    {["Public", "Private", "Faith-based", "Other"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Latitude">
                  <input
                    name="latitude"
                    type="number"
                    step="any"
                    min="-90"
                    max="90"
                    defaultValue={selected?.latitude}
                  />
                </Field>
                <Field label="Longitude">
                  <input
                    name="longitude"
                    type="number"
                    step="any"
                    min="-180"
                    max="180"
                    defaultValue={selected?.longitude}
                  />
                </Field>
                <Field label="Phone">
                  <input name="phone" defaultValue={selected?.phone} />
                </Field>
                <Field label="Email">
                  <input
                    name="email"
                    type="email"
                    defaultValue={selected?.email}
                  />
                </Field>
                <Field label="Status">
                  <select
                    name="active"
                    defaultValue={selected?.active === false ? "false" : "true"}
                  >
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                  </select>
                </Field>
              </div>
            </Form>
          )}
          {modal === "Sub-district" && (
            <Form onSubmit={(d) => save("/api/subdistricts", d)}>
              <Field label="Name">
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
          )}
          {modal === "Community" && (
            <Form onSubmit={(d) => save("/api/communities", d)}>
              <Field label="Community name">
                <input name="name" required />
              </Field>
              <Field label="CHPS zone">
                <input name="chps_zone" />
              </Field>
              <Field label="Parent facility">
                <Select name="facility_id" options={structure.facilities} />
              </Field>
            </Form>
          )}
          {modal === "Clients" && (
            <Form
              onSubmit={(d) =>
                save("/api/clients", {
                  ...d,
                  community_id: d.community_id || null,
                })
              }
            >
              <div className="form-grid">
                <Field label="Full name">
                  <input name="name" required />
                </Field>
                <Field label="Client reference">
                  <input name="reference" required />
                </Field>
                <Field label="Date of birth">
                  <input
                    name="date_of_birth"
                    type="date"
                    max={dateToday()}
                    required
                  />
                </Field>
                <Field label="Sex">
                  <select name="sex">
                    {["Female", "Male", "Other", "Unknown"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Facility">
                  <Select name="facility_id" options={structure.facilities} />
                </Field>
                <Field label="Community">
                  <Select
                    name="community_id"
                    options={structure.communities}
                    required={false}
                  />
                </Field>
                <Field label="Phone (optional)">
                  <input name="phone" />
                </Field>
              </div>
            </Form>
          )}
          {modal === "Encounters" && (
            <ProgrammeEncounter
              registry={registry}
              enabled={enabled}
              clients={clients}
              initial={programme}
              role={role}
              onSave={async (d) => {
                if (!navigator.onLine) {
                  if (!offlineCapture.current)
                    throw Error(
                      "Encrypted capture is unavailable on this page.",
                    );
                  await offlineCapture.current.queue(d);
                  setModal("");
                  notify(
                    "Entry encrypted on this device. Sync it after reconnecting.",
                  );
                } else await save("/api/encounters", d);
              }}
            />
          )}
          {modal === "Action centre" && (
            <Form
              onSubmit={(d) =>
                save("/api/actions", {
                  ...d,
                  facility_id: d.facility_id || null,
                  assigned_to: d.assigned_to || null,
                  indicator_id: selected?.indicator_id || null,
                })
              }
            >
              <Field label="Action title">
                <input name="title" defaultValue={selected?.title} required />
              </Field>
              <Field label="Problem or signal">
                <textarea
                  name="problem"
                  defaultValue={selected?.problem}
                  required
                />
              </Field>
              <div className="form-grid">
                <Field label="Facility">
                  <Select
                    name="facility_id"
                    options={structure.facilities}
                    required={!!member?.facility_id}
                  />
                </Field>
                <Field
                  label="Responsible officer"
                  hint="Leave blank for district assignment later."
                >
                  <Select
                    name="assigned_to"
                    options={roleOptions}
                    required={false}
                  />
                  <button
                    type="button"
                    className="text-button"
                    onClick={() =>
                      api<Row[]>("/api/users")
                        .then(setRoleOptions)
                        .catch((e) => setError(e.message))
                    }
                  >
                    Load team
                  </button>
                </Field>
                <Field label="Due date">
                  <input
                    name="due_date"
                    type="date"
                    defaultValue={dateToday()}
                    required
                  />
                </Field>
                <Field label="Priority">
                  <select
                    name="priority"
                    defaultValue={selected?.priority || "Medium"}
                  >
                    {["Low", "Medium", "High", "Urgent"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </Field>
              </div>
            </Form>
          )}
          {modal === "Update action" && selected && (
            <>
              <div className="record-summary">
                <h3>{selected.title}</h3>
                <p>{selected.problem}</p>
                <Badge>{selected.priority}</Badge>
                <span>Due {selected.due_date}</span>
              </div>
              <Form
                label="Update action"
                onSubmit={(d) =>
                  save(`/api/actions/${selected.id}`, d, "PATCH")
                }
              >
                <Field label="Status">
                  <select name="status" defaultValue={selected.status}>
                    {["Open", "In progress", "Completed", "Cancelled"].map(
                      (v) => (
                        <option key={v}>{v}</option>
                      ),
                    )}
                  </select>
                </Field>
                <Field
                  label="Outcome / follow-up findings"
                  hint="Required to complete the action."
                >
                  <textarea
                    name="outcome"
                    rows={4}
                    defaultValue={selected.outcome}
                  />
                </Field>
              </Form>
            </>
          )}
          {modal === "Indicators" && (
            <IndicatorEditor
              enabled={enabled}
              onSave={(d) => save("/api/indicators", d)}
            />
          )}
          {(modal === "Monthly reports" || modal === "Edit report") && (
            <Form
              onSubmit={(d) => {
                const values = indicators.map((i) => ({
                  indicator_id: i.id,
                  numerator: Number(d[`n_${i.id}`]),
                  denominator: Number(d[`d_${i.id}`]),
                }));
                return save(
                  selected ? `/api/reports/${selected.id}` : "/api/reports",
                  { facility_id: d.facility_id, period: d.period, values },
                  selected ? "PUT" : "POST",
                );
              }}
            >
              <Field label="Facility">
                <Select
                  name="facility_id"
                  options={structure.facilities}
                  value={selected?.facility_id}
                  onChange={(v) =>
                    selected && setSelected({ ...selected, facility_id: v })
                  }
                />
              </Field>
              <Field label="Reporting month">
                <input
                  name="period"
                  type="month"
                  required
                  defaultValue={selected?.period || dateToday().slice(0, 7)}
                />
              </Field>
              {!indicators.length && (
                <div className="error">
                  Configure approved indicators before creating a report.
                </div>
              )}
              {indicators.map((i) => (
                <div className="report-indicator" key={i.id}>
                  <h4>{i.name}</h4>
                  <p>{i.definition}</p>
                  <div className="form-grid">
                    <Field label={`Numerator: ${i.numerator_definition}`}>
                      <input
                        name={`n_${i.id}`}
                        type="number"
                        min="0"
                        step="1"
                        required
                        defaultValue={
                          selected?.values?.find(
                            (v: Row) => v.indicator_id === i.id,
                          )?.numerator
                        }
                      />
                    </Field>
                    <Field label={`Denominator: ${i.denominator_definition}`}>
                      <input
                        name={`d_${i.id}`}
                        type="number"
                        min="0"
                        step="1"
                        required
                        defaultValue={
                          selected?.values?.find(
                            (v: Row) => v.indicator_id === i.id,
                          )?.denominator
                        }
                      />
                    </Field>
                  </div>
                </div>
              ))}
            </Form>
          )}
          {modal === "Report review" && selected && (
            <>
              <div className="record-summary">
                <h3>
                  {facilityName(selected.facility_id)} · {selected.period}
                </h3>
                <Badge>{selected.state}</Badge>
                <span>Revision {selected.revision}</span>
              </div>
              <Table
                rows={selected.values.map((v: Row) => ({
                  ...v,
                  id: v.indicator_id,
                  name: indicators.find((i) => i.id === v.indicator_id)?.name,
                }))}
                columns={[
                  { key: "name", label: "Indicator" },
                  { key: "numerator", label: "Numerator" },
                  { key: "denominator", label: "Denominator" },
                ]}
              />
              <div className="admin-tabs">
                <button
                  className="secondary"
                  onClick={async () => {
                    try {
                      setReportJob(
                        await post(`/api/reports/${selected.id}/jobs`, {
                          format: "pdf",
                        }),
                      );
                    } catch (e) {
                      notify((e as Error).message);
                    }
                  }}
                >
                  Queue PDF report
                </button>
                {reportJob && (
                  <>
                    <span>Job: {reportJob.state}</span>
                    <button
                      className="secondary"
                      onClick={async () => {
                        setReportJob(
                          await api(`/api/report-jobs/${reportJob.id}`),
                        );
                      }}
                    >
                      Check job status
                    </button>
                    {reportJob.state === "Completed" && (
                      <button
                        className="secondary"
                        onClick={() =>
                          download(
                            `/api/report-jobs/${reportJob.id}/download`,
                            `nutrition-report-${selected.period}.pdf`,
                          )
                        }
                      >
                        Download generated report
                      </button>
                    )}
                  </>
                )}
              </div>
              <div className="admin-tabs">
                <button
                  className="secondary"
                  onClick={() =>
                    download(
                      `/api/reports/${selected.id}/export/pdf`,
                      `nutrition-report-${selected.period}.pdf`,
                    ).catch((e) => notify(e.message))
                  }
                >
                  Download PDF
                </button>
                <button
                  className="secondary"
                  onClick={() =>
                    download(
                      `/api/reports/${selected.id}/export/xlsx`,
                      `nutrition-report-${selected.period}.xlsx`,
                    ).catch((e) => notify(e.message))
                  }
                >
                  Download Excel
                </button>
              </div>
              {!isAggregate &&
                ["Draft", "Returned"].includes(selected.state) && (
                  <button
                    className="secondary"
                    onClick={() => setModal("Edit report")}
                  >
                    Edit report values
                    <Plus size={14} />
                  </button>
                )}
              {!isAggregate && selected.state !== "Locked" && (
                <Form
                  label="Apply transition"
                  onSubmit={(d) =>
                    save(`/api/reports/${selected.id}/transition`, d)
                  }
                >
                  <Field label="Next workflow state">
                    <select name="state">
                      {(selected.state === "Draft" ||
                      selected.state === "Returned"
                        ? ["Submitted"]
                        : selected.state === "Submitted"
                          ? ["Verified", "Returned"]
                          : selected.state === "Verified"
                            ? ["Approved", "Returned"]
                            : selected.state === "Approved"
                              ? ["Locked"]
                              : []
                      ).map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Review reason">
                    <textarea name="reason" />
                  </Field>
                </Form>
              )}
              {isAdmin && ["Approved", "Locked"].includes(selected.state) && (
                <Form
                  label="Open authorized amendment"
                  onSubmit={(d) => save(`/api/reports/${selected.id}/amend`, d)}
                >
                  <Field
                    label="Amendment reason"
                    hint="Previous values remain in the audit record."
                  >
                    <textarea name="reason" minLength={10} required />
                  </Field>
                </Form>
              )}
            </>
          )}
          {[
            "Supportive supervision",
            "Interventions",
            "Schools",
            "Commodity visibility",
          ].includes(modal) && (
            <Form
              onSubmit={(d) => {
                const { title, facility_id, ...details } = d;
                return save(
                  `/api/registers/${{ "Supportive supervision": "supervision", Interventions: "interventions", Schools: "schools", "Commodity visibility": "commodities" }[modal]}`,
                  { title, facility_id: facility_id || null, details },
                );
              }}
            >
              <Field
                label={
                  modal === "Schools"
                    ? "School name"
                    : modal === "Commodity visibility"
                      ? "Commodity / supply item"
                      : "Activity title"
                }
              >
                <input name="title" required />
              </Field>
              <Field label="Facility">
                <Select
                  name="facility_id"
                  options={structure.facilities}
                  required={modal !== "Interventions"}
                />
              </Field>
              {modal === "Supportive supervision" && (
                <>
                  <Field label="Visit date">
                    <input
                      name="date"
                      type="date"
                      required
                      defaultValue={dateToday()}
                    />
                  </Field>
                  <Field label="Checklist and findings">
                    <textarea name="findings" required rows={4} />
                  </Field>
                  <Field label="Corrective action">
                    <input name="corrective_action" />
                  </Field>
                  <Field label="Follow-up deadline">
                    <input name="followup_date" type="date" />
                  </Field>
                </>
              )}
              {modal === "Interventions" && (
                <>
                  <Field label="Date">
                    <input
                      name="date"
                      type="date"
                      required
                      defaultValue={dateToday()}
                    />
                  </Field>
                  <Field label="Linked indicator">
                    <Select
                      name="indicator_id"
                      options={indicators}
                      required={false}
                    />
                  </Field>
                  <Field label="Linked community">
                    <Select
                      name="community_id"
                      options={structure.communities}
                      required={false}
                    />
                  </Field>
                  <Field label="Problem being addressed">
                    <textarea name="problem" required />
                  </Field>
                  <Field label="Target population">
                    <input name="target_population" />
                  </Field>
                  <Field label="Number reached">
                    <input
                      name="number_reached"
                      type="number"
                      min="0"
                      defaultValue="0"
                    />
                  </Field>
                  <Field label="Responsible team">
                    <input name="responsible_team" required />
                  </Field>
                  <Field label="Cost (GHS), if authorized">
                    <input name="cost" type="number" min="0" step="0.01" />
                  </Field>
                  <Field label="Observed outcome">
                    <textarea name="outcome" />
                  </Field>
                  <Field label="Follow-up date">
                    <input name="followup_date" type="date" />
                  </Field>
                </>
              )}
              {modal === "Schools" && (
                <>
                  <Field label="School type">
                    <select name="school_type">
                      {[
                        "Primary",
                        "Junior High",
                        "Senior High",
                        "Technical/Vocational",
                        "Other",
                      ].map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Community">
                    <input name="community" />
                  </Field>
                  <Field label="Eligible population">
                    <input
                      name="eligible_population"
                      type="number"
                      min="0"
                      defaultValue="0"
                    />
                  </Field>
                  <Field label="Programme status">
                    <select name="programme_status">
                      <option>Active</option>
                      <option>Inactive</option>
                    </select>
                  </Field>
                </>
              )}
              {modal === "Commodity visibility" && (
                <>
                  <Field label="Reporting month">
                    <input
                      name="period"
                      type="month"
                      required
                      defaultValue={dateToday().slice(0, 7)}
                    />
                  </Field>
                  <div className="form-grid">
                    {[
                      ["opening", "Opening balance"],
                      ["received", "Received"],
                      ["used", "Used / distributed"],
                      ["loss", "Loss / adjustment"],
                      ["stockout_days", "Stock-out days"],
                    ].map(([k, l]) => (
                      <Field label={l} key={k}>
                        <input
                          name={k}
                          type="number"
                          min="0"
                          required
                          defaultValue="0"
                        />
                      </Field>
                    ))}
                  </div>
                  <Field label="Expiry date, if applicable">
                    <input name="expiry" type="date" />
                  </Field>
                  <p className="muted">
                    Closing balance is calculated and validated by the API.
                  </p>
                </>
              )}
            </Form>
          )}
          {modal === "Users" && (
            <Form
              onSubmit={(d) =>
                save("/api/users", {
                  ...d,
                  subdistrict_id: d.subdistrict_id || null,
                  facility_id: d.facility_id || null,
                  community_id: d.community_id || null,
                })
              }
            >
              <Field label="Full name">
                <input name="name" required />
              </Field>
              <Field label="Email">
                <input name="email" type="email" required />
              </Field>
              <Field label="Secure initial password">
                <input
                  name="password"
                  type="password"
                  minLength={12}
                  required
                  autoComplete="new-password"
                />
              </Field>
              <Field label="Role">
                <select name="role">
                  {[
                    "District Nutrition Officer",
                    "Nutritionist/Dietitian",
                    "Facility In-Charge",
                    "Midwife/ANC Staff",
                    "Community Health Nurse",
                    "School Health/GIFTS Officer",
                    "Field/CHPS Worker",
                    "Data Officer",
                    "Viewer",
                  ].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </Field>
              <Field label="Health sub-district scope (optional)">
                <Select
                  name="subdistrict_id"
                  options={structure.subdistricts}
                  required={false}
                />
              </Field>
              <Field label="Facility scope">
                <Select
                  name="facility_id"
                  options={structure.facilities}
                  required={false}
                />
              </Field>
              <Field label="Community scope (required for field workers)">
                <Select
                  name="community_id"
                  options={structure.communities}
                  required={false}
                />
              </Field>
            </Form>
          )}
          {modal === "Bulk import" && (
            <>
              <p className="muted">
                CSV/XLSX columns: facility_name, facility_code, facility_type,
                subdistrict, community, ownership, latitude, longitude, status.
              </p>
              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  const form = new FormData();
                  form.append("file", file);
                  try {
                    setImportResult(
                      await api("/api/facilities/import/validate", {
                        method: "POST",
                        body: form,
                      }),
                    );
                  } catch (err) {
                    notify((err as Error).message);
                  }
                }}
              />
              {importResult && (
                <>
                  <div className="import-counts">
                    <Badge>{importResult.valid} valid</Badge>
                    <Badge>{importResult.invalid} invalid</Badge>
                    <Badge>{importResult.duplicates} duplicates</Badge>
                  </div>
                  <Table
                    rows={importResult.rows.map((r: Row) => ({
                      ...r,
                      id: r.row,
                    }))}
                    columns={[
                      { key: "row", label: "Row" },
                      { key: "name", label: "Facility" },
                      { key: "status", label: "Validation" },
                      {
                        key: "errors",
                        label: "Issues",
                        render: (r) => r.errors.join("; "),
                      },
                    ]}
                  />
                  <p className="muted">
                    Correct invalid or duplicate rows in the source file and
                    upload again. Only a fully valid import can be committed.
                  </p>
                  <button
                    className="primary"
                    disabled={
                      !importResult.valid ||
                      importResult.invalid > 0 ||
                      importResult.duplicates > 0
                    }
                    onClick={() =>
                      save(
                        "/api/facilities/import",
                        importResult.rows.map((r: Row) => r.data),
                      ).catch((e) => notify(e.message))
                    }
                  >
                    Import {importResult.valid} facilities
                    <CheckCircle2 size={16} />
                  </button>
                </>
              )}
            </>
          )}
          {modal === "Facility profile" && selected && (
            <>
              <div className="record-summary">
                <h3>{selected.name}</h3>
                <p>
                  {selected.facility_type || "Facility nutrition performance"}
                </p>
              </div>
              {(() => {
                const profile = dash?.facility_profiles.find(
                  (f: Row) =>
                    f.facility_id === (selected.id || selected.facility_id),
                );
                return profile ? (
                  <>
                    <div className="review-grid">
                      {Object.entries(profile.components).map(([key, v]) => (
                        <div key={key}>
                          <small>{key}</small>
                          <strong>{String(v)}%</strong>
                        </div>
                      ))}
                      <div>
                        <small>Open actions</small>
                        <strong>{profile.open_actions}</strong>
                      </div>
                    </div>
                    <p className="muted">
                      Consistency checks enabled programme definitions.
                      Duplicate rate measures repeated normalized client
                      references within this facility; lower is better. Missing
                      components are excluded from the weighted score.
                    </p>
                    <FacilityPerformance
                      id={selected.id || selected.facility_id}
                    />
                    <h4>Supportive supervision</h4>
                    <button
                      className="text-button"
                      onClick={() => {
                        setModal("");
                        navigate("Supportive supervision");
                      }}
                    >
                      Open supervision register
                      <ArrowRight size={14} />
                    </button>
                  </>
                ) : (
                  <Empty title="No reporting profile yet" />
                );
              })()}
            </>
          )}
          {modal === "Client history" && selected && (
            <ClientHistory
              client={selected}
              facilityName={facilityName(selected.facility_id)}
            />
          )}
          {["Register details", "What’s new"].includes(modal) && selected && (
            <div className="review-grid">
              {Object.entries(selected.details || selected)
                .filter(
                  ([k]) =>
                    !["organization_id", "entered_by", "modified_by"].includes(
                      k,
                    ),
                )
                .map(([k, v]) => (
                  <div key={k}>
                    <small>{k.replaceAll("_", " ")}</small>
                    <strong>
                      {typeof v === "object"
                        ? JSON.stringify(v)
                        : String(v ?? "—")}
                    </strong>
                  </div>
                ))}
            </div>
          )}
          {modal === "Programme configuration" && (
            <Form
              label="Update programmes"
              onSubmit={async (d) => {
                await save(
                  "/api/configuration",
                  {
                    ...org.configuration,
                    reporting_officer:
                      org.configuration.reporting_officer || "",
                    logo_url: org.configuration.logo_url || "",
                    programmes: Object.entries(d)
                      .filter(([, v]) => v === "on")
                      .map(([k]) => k),
                  },
                  "PUT",
                );
                await login();
              }}
            >
              {registry.map((p) => (
                <label className="programme-option" key={p.code}>
                  <input
                    type="checkbox"
                    name={p.code}
                    defaultChecked={enabled.includes(p.code)}
                  />
                  {p.name}
                </label>
              ))}
            </Form>
          )}
        </Modal>
      )}
    </div>
  );
}
function ClientHistory({
  client,
  facilityName,
}: {
  client: Row;
  facilityName: string;
}) {
  const [rows, setRows] = useState<Row[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    api<Row[]>(`/api/encounters?client_id=${client.id}`)
      .then(setRows)
      .catch((e) => setError(e.message));
  }, [client.id]);
  return (
    <>
      <div className="record-summary">
        <h3>{client.name}</h3>
        <p>
          {client.reference} · {facilityName}
        </p>
      </div>
      {error && <div className="error">{error}</div>}
      {rows.length ? (
        rows.map((r) => (
          <div className="history-item" key={r.id}>
            <small>
              {r.visit_date} · {programmeLabels[r.programme] || r.programme}
            </small>
            <h4>{r.assessment}</h4>
            <Badge>{r.risk}</Badge>
            <p>
              {r.outcome || "No outcome recorded"}
              {r.followup_date && ` · Follow-up ${r.followup_date}`}
            </p>
          </div>
        ))
      ) : (
        <Empty title="No encounters recorded yet" />
      )}
    </>
  );
}

function FacilityPerformance({ id }: { id: string }) {
  const [profile, setProfile] = useState<Row | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    api<Row>(`/api/facilities/${id}/profile`)
      .then(setProfile)
      .catch((e) => setError(e.message));
  }, [id]);
  return error ? (
    <div className="error">{error}</div>
  ) : profile ? (
    <>
      <div className="review-grid">
        <div>
          <small>Completed client follow-ups</small>
          <strong>{profile.followup_completed}</strong>
        </div>
        <div>
          <small>Supervision visits</small>
          <strong>
            {profile.supervision_visits} · latest{" "}
            {profile.last_supervision || "None"}
          </strong>
        </div>
        <div>
          <small>Programmes</small>
          <strong>
            {profile.programme_coverage
              .map((p: string) => programmeLabels[p] || p)
              .join(", ")}
          </strong>
        </div>
      </div>
      <h4 style={{ marginTop: 20 }}>Facility indicator history</h4>
      {profile.trends.length ? (
        <Table
          rows={profile.trends.map((r: Row) => ({ ...r, id: r.period }))}
          columns={[
            { key: "period", label: "Period" },
            ...profile.indicators.map((i: Row) => ({
              key: i.name,
              label: i.name,
              render: (r: Row) =>
                r[i.name] == null ? "Not measured" : `${r[i.name]}%`,
            })),
          ]}
        />
      ) : (
        <p className="muted">No approved facility indicator reports yet.</p>
      )}
    </>
  ) : (
    <p className="muted">Loading facility performance…</p>
  );
}
