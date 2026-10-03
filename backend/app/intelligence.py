"""Approved-report comparisons, explicit denominators and explainable signals."""

from collections import defaultdict
from datetime import date
from fastapi import Depends, HTTPException, Query
from sqlalchemy import select
from .models import *
from .db import get_db
from .security import current_user, authorized_memberships, AGGREGATE, ADMIN, audit
from .schemas import SignalActionIn


def previous_period():
    today = date.today()
    return f"{today.year-1 if today.month==1 else today.year}-{12 if today.month==1 else today.month-1:02d}"


def intelligence(db, ids, period=None, member=None):
    from . import main as core

    organizations = list(db.scalars(select(Organization).where(Organization.id.in_(ids))))
    regions = {r.id: r.name for r in db.scalars(select(Region))}
    facilities = list(
        db.scalars(
            core.scoped_query(Facility, member)
            if member
            else select(Facility).where(Facility.organization_id.in_(ids))
        )
    )
    facility_ids = {f.id for f in facilities}
    reports = list(
        db.scalars(
            select(Report).where(
                Report.organization_id.in_(ids), Report.facility_id.in_(facility_ids)
            )
        )
    )
    approved = [r for r in reports if r.state in {"Approved", "Locked"}]
    period = period or previous_period()
    definitions = {
        i.id: i for i in db.scalars(select(Indicator).where(Indicator.organization_id.in_(ids)))
    }
    standards = {s.id: s for s in db.scalars(select(StandardIndicator))}
    catalogue = {
        s.id: dict(
            id=s.id,
            code=s.code,
            name=s.name,
            version=s.version,
            target=s.target,
            direction=s.direction,
        )
        for s in standards.values()
    }
    totals = defaultdict(lambda: [0, 0])
    per_region = defaultdict(lambda: [0, 0])
    local = defaultdict(lambda: [0, 0])
    by_org = {o.id: o for o in organizations}
    for r in approved:
        for v in r.values:
            definition = definitions.get(v["indicator_id"])
            if not definition:
                continue
            # A standard version is a comparable definition; local-only indicators are not pooled nationally.
            local[(r.organization_id, definition.id, r.period)][0] += v["numerator"]
            local[(r.organization_id, definition.id, r.period)][1] += v["denominator"]
            if definition.standard_id and definition.standard_id in standards:
                key = (definition.standard_id, r.period)
                totals[key][0] += v["numerator"]
                totals[key][1] += v["denominator"]
                key = (by_org[r.organization_id].region_id, definition.standard_id, r.period)
                per_region[key][0] += v["numerator"]
                per_region[key][1] += v["denominator"]
    coverage = lambda n, d: round(100 * n / d, 2) if d else None
    trends = [
        dict(**catalogue[s], period=p, numerator=n, denominator=d, value=coverage(n, d))
        for (s, p), (n, d) in sorted(totals.items(), key=lambda item: item[0][1])
    ]
    comparisons = [
        dict(
            **catalogue[s],
            region_id=region,
            region=regions[region],
            numerator=n,
            denominator=d,
            value=coverage(n, d),
        )
        for (region, s, p), (n, d) in per_region.items()
        if p == period
    ]
    signals = []
    organization_rows = []
    stock = list(
        db.scalars(
            select(OperationalRecord).where(
                OperationalRecord.organization_id.in_(ids), OperationalRecord.kind == "commodities"
            )
        )
    )
    actions = list(
        db.scalars(select(Action).where(Action.organization_id.in_(ids), Action.client_id == None))
    )
    for o in organizations:
        active = {f.id for f in facilities if f.organization_id == o.id and f.active}
        submitted = {
            r.facility_id
            for r in reports
            if r.organization_id == o.id
            and r.period == period
            and r.state != "Draft"
            and r.facility_id in active
        }
        verified = {
            r.facility_id
            for r in approved
            if r.organization_id == o.id and r.period == period and r.facility_id in active
        }
        district_signals = []
        for i in definitions.values():
            if i.organization_id != o.id:
                continue
            n, d = local[(o.id, i.id, period)]
            value = coverage(n, d)
            if value is None:
                continue
            prior = sorted(
                p
                for org, indicator, p in local
                if org == o.id
                and indicator == i.id
                and p < period
                and local[(org, indicator, p)][1]
            )
            previous = coverage(*local[(o.id, i.id, prior[-1])]) if prior else None
            delta = round(value - previous, 2) if previous is not None else None
            gap = round(
                max(0, i.target - value if i.direction == "higher" else value - i.target), 2
            )
            threshold = o.configuration.get("deterioration_threshold_pp", 5)
            deteriorating = delta is not None and (
                delta <= -threshold if i.direction == "higher" else delta >= threshold
            )
            if gap or deteriorating:
                key = f"{i.id}:{period}"
                linked = next(
                    (a for a in actions if a.organization_id == o.id and a.signal_key == key), None
                )
                signal = dict(
                    id=key,
                    organization_id=o.id,
                    organization=o.name,
                    indicator_id=i.id,
                    title=i.name,
                    period=period,
                    value=value,
                    target=i.target,
                    gap_pp=gap,
                    change_pp=delta,
                    previous_period=prior[-1] if prior else None,
                    kind="Deterioration" if deteriorating else "Target gap",
                    action_id=linked.id if linked else None,
                    action_status=linked.status if linked else None,
                    stockout_days=sum(
                        float(r.details.get("stockout_days", 0))
                        for r in stock
                        if r.organization_id == o.id and r.details.get("period") == period
                    ),
                    explanation="Review reporting, service access, follow-up and commodity availability. Coinciding activity and indicator changes do not establish causation.",
                )
                signals.append(signal)
                district_signals.append(signal)
        organization_rows.append(
            dict(
                id=o.id,
                name=o.name,
                region=regions.get(o.region_id),
                region_id=o.region_id,
                health_district_id=o.health_district_id,
                expected_facilities=len(active),
                submitted_facilities=len(submitted),
                approved_facilities=len(verified),
                reporting_completeness=coverage(len(submitted), len(active)),
                approved_completeness=coverage(len(verified), len(active)),
                open_signals=len(district_signals),
                target_gap_pp=round(sum(s["gap_pp"] for s in district_signals), 2),
            )
        )
    organization_rows.sort(
        key=lambda o: (-o["open_signals"], -(100 - (o["reporting_completeness"] or 0)))
    )
    return dict(
        period=period,
        organizations=organization_rows,
        standards=list(catalogue.values()),
        trends=trends,
        regional_comparison=comparisons,
        signals=signals,
        approved_reports=sum(r.period == period for r in approved),
        expected_facilities=sum(o["expected_facilities"] for o in organization_rows),
        submitted_facilities=sum(o["submitted_facilities"] for o in organization_rows),
        methodology="Approved/locked reports only for indicator estimates. National comparisons pool matching standard indicator versions; local-only indicators remain district-specific. Reporting completeness is distinct currently active facilities submitted for the selected month / currently active facilities. Priority order uses number of indicator exceptions, then reporting gaps; it is not a clinical risk score. No denominator means no estimate. No causal attribution.",
    )


def install(app):
    from . import main as core

    @app.get("/api/intelligence")
    def overview(
        organization_id: str | None = None,
        region_id: str | None = None,
        period: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
        user=Depends(current_user),
        db=Depends(get_db),
    ):
        members = authorized_memberships(db, user.id)
        if organization_id:
            member = next((m for m in members if m.organization_id == organization_id), None)
            if not member or member.role == "System Administrator":
                raise HTTPException(403, "Organization analytics are outside your scope")
            ids = [organization_id]
        else:
            member = None
            members = authorized_memberships(db, user.id, aggregate_only=True)
            grants = list(
                db.scalars(
                    select(AccessGrant).where(
                        AccessGrant.user_id == user.id, AccessGrant.active == True
                    )
                )
            )
            if not members and not any(
                (g.level == "NATIONAL" and g.role == "National Nutrition Administrator" and not g.region_id)
                or (g.level == "REGION" and g.role == "Regional Nutrition Officer" and g.region_id)
                for g in grants
            ):
                raise HTTPException(403, "Assigned aggregate scope required")
            ids = [m.organization_id for m in members]
        if region_id:
            ids = [
                o.id
                for o in db.scalars(
                    select(Organization).where(
                        Organization.id.in_(ids), Organization.region_id == region_id
                    )
                )
            ]
        return intelligence(db, ids, period, member)

    @app.post("/api/signals/actions", status_code=201)
    def action_from_signal(data: SignalActionIn, m=Depends(core.scope), db=Depends(get_db)):
        core.require(m, ADMIN)
        core.owned(db, Indicator, data.indicator_id, m)
        signal = next(
            (
                s
                for s in intelligence(db, [m.organization_id], data.period, m)["signals"]
                if s["indicator_id"] == data.indicator_id
            ),
            None,
        )
        if not signal:
            raise HTTPException(422, "No active signal for this indicator and period")
        key = f"{data.indicator_id}:{data.period}"
        if db.scalar(
            select(Action.id).where(
                Action.organization_id == m.organization_id, Action.signal_key == key
            )
        ):
            raise HTTPException(409, "An action already addresses this signal")
        from .schemas import ActionIn

        # Reuse operational assignee and facility validation, commit atomically after adding signal identity.
        payload = ActionIn(
            title=f"{signal['kind']}: {signal['title']}"[:180],
            problem=data.problem,
            indicator_id=data.indicator_id,
            facility_id=data.facility_id,
            assigned_to=data.assigned_to,
            due_date=data.due_date,
            priority="High",
        )
        row = core.create_action(payload, m, db)
        row.signal_key = key
        row.source = f"Approved indicator signal {data.period}"
        audit(db, m, "signal.action_linked", row.id, {"signal_key": key})
        return core.save(db, row)
