import { useState } from "react";
import Intelligence from "./Intelligence";
import MasterDataAdmin from "./MasterDataAdmin";
import RegistryAdmin from "./RegistryAdmin";
import { Brand, type Row } from "./components";
export default function ScopeOverview({
  me,
  environment,
  onSignOut,
  onOpenOrganization,
}: {
  me: Row;
  environment: string;
  onSignOut: () => Promise<void>;
  onOpenOrganization: (id: string) => void;
}) {
  const [tab, setTab] = useState("Nutrition situation");
  const national = me.grants?.some(
    (g: Row) =>
      g.level === "NATIONAL" && g.role === "National Nutrition Administrator",
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
        <div className="eyebrow">
          AUTHORIZED {national ? "NATIONAL" : "REGIONAL"} SCOPE
        </div>
        <h1>
          {national
            ? "Ghana nutrition situation"
            : "Regional nutrition situation"}
        </h1>
        <p>
          {me.user.name} · Aggregate programme oversight within your assigned
          scope.
        </p>
        <div className="admin-tabs">
          {[
            "Nutrition situation",
            ...(national ? ["Programmes", "Indicator standards", "Master data"] : []),
          ].map((t) => (
            <button
              key={t}
              className={tab === t ? "primary" : "secondary"}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
        {tab === "Nutrition situation" ? (
          <Intelligence onOpenOrganization={onOpenOrganization} />
        ) : tab === "Master data" ? <MasterDataAdmin /> : (
          <RegistryAdmin
            section={tab as "Programmes" | "Indicator standards"}
          />
        )}
      </main>
    </div>
  );
}
