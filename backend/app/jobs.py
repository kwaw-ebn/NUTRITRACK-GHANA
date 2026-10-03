"""Durable report queue with database leases and permission revalidation."""

from datetime import timedelta
from fastapi import Depends, BackgroundTasks, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, or_
from cryptography.fernet import Fernet
from .db import SessionLocal, get_db
from .models import ReportJob, User, Audit
from .security import authorized_memberships, utc, aware
from .config import settings
from .schemas import ReportJobIn


def run_job(id):
    from . import main as core

    with SessionLocal() as db:
        row = db.scalar(
            select(ReportJob)
            .where(
                ReportJob.id == id,
                or_(
                    ReportJob.state == "Queued",
                    (ReportJob.state == "Running") & (ReportJob.lease_until < utc()),
                ),
            )
            .with_for_update(skip_locked=True)
        )
        if not row:
            return
        row.state = "Running"
        row.lease_until = utc() + timedelta(minutes=5)
        db.commit()
        try:
            user = db.get(User, row.user_id)
            if not user or not user.active:
                raise ValueError("Inactive user")
            member = next(
                (
                    m
                    for m in authorized_memberships(db, user.id)
                    if m.organization_id == row.organization_id
                ),
                None,
            )
            if not member:
                raise ValueError("Permission withdrawn")
            endpoint = next(
                r.endpoint for r in core.app.routes if getattr(r, "name", None) == "export_report"
            )
            result = endpoint(row.report_id, row.format, member, db)
            row = db.get(ReportJob, id)
            row.encrypted_output = (
                Fernet(settings().evidence_encryption_key.encode()).encrypt(result.body).decode()
            )
            row.state = "Completed"
            row.lease_until = None
            row.error = None
            db.add(
                Audit(
                    actor_id=user.id,
                    organization_id=row.organization_id,
                    event="report_job.completed",
                    entity_id=id,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            row = db.get(ReportJob, id)
            row.state = "Failed"
            row.lease_until = None
            row.error = "Report generation failed or access was withdrawn. Review service configuration and audit activity."
            db.add(
                Audit(organization_id=row.organization_id, event="report_job.failed", entity_id=id)
            )
            db.commit()


def install(app):
    from . import main as core

    @app.post("/api/reports/{id}/jobs", status_code=202)
    def enqueue(
        id: str,
        data: ReportJobIn,
        background: BackgroundTasks,
        m=Depends(core.scope),
        db=Depends(get_db),
    ):
        core.require(m, set(core.ROLES) - {"System Administrator"})
        report = core.owned(db, core.Report, id, m)
        if not settings().evidence_encryption_key:
            raise HTTPException(503, "Secure generated-report storage is not configured")
        row = ReportJob(
            organization_id=m.organization_id,
            user_id=m.user_id,
            report_id=id,
            facility_id=report.facility_id,
            format=data.format,
        )
        db.add(row)
        db.flush()
        core.audit(db, m, "report_job.queued", row.id)
        db.commit()
        background.add_task(run_job, row.id)
        return {"id": row.id, "state": "Queued"}

    @app.get("/api/report-jobs/{id}")
    def status(id: str, m=Depends(core.scope), db=Depends(get_db)):
        core.require(m, set(core.ROLES) - {"System Administrator"})
        row = core.owned(db, ReportJob, id, m)
        return {"id": row.id, "state": row.state, "format": row.format, "error": row.error}

    @app.get("/api/report-jobs/{id}/download")
    def download(id: str, m=Depends(core.scope), db=Depends(get_db)):
        core.require(m, set(core.ROLES) - {"System Administrator"})
        row = core.owned(db, ReportJob, id, m)
        core.owned(db, core.Report, row.report_id, m)
        if row.state != "Completed" or not row.encrypted_output:
            raise HTTPException(409, "Report file is not ready")
        output = Fernet(settings().evidence_encryption_key.encode()).decrypt(
            row.encrypted_output.encode()
        )
        core.audit(db, m, "report_job.downloaded", id)
        db.commit()
        mime = (
            "application/pdf"
            if row.format == "pdf"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        return Response(
            output,
            media_type=mime,
            headers={
                "Content-Disposition": f'attachment; filename="nutrition-report.{row.format}"'
            },
        )
