"""Run as a supervised worker to recover pending report jobs after process restarts."""

import argparse, time
from sqlalchemy import select, or_
from .db import SessionLocal
from .models import ReportJob
from .security import utc
from .jobs import run_job


def process():
    with SessionLocal() as db:
        ids = list(
            db.scalars(
                select(ReportJob.id)
                .where(
                    or_(
                        ReportJob.state == "Queued",
                        (ReportJob.state == "Running") & (ReportJob.lease_until < utc()),
                    )
                )
                .order_by(ReportJob.created_at)
                .limit(20)
            )
        )
    for id in ids:
        run_job(id)
    return len(ids)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        process()
        if args.once:
            break
        time.sleep(5)
