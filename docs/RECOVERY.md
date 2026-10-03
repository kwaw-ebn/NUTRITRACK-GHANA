# Backup and recovery runbook

Status: designed, not restore-tested in this workspace. The UI displays backup status as unverified; it does not assert protection.

Proposed pilot objectives (must be agreed with the deployment owner): RPO ≤24 hours for a daily snapshot policy; RTO ≤8 hours after restore exercise and incident authorization. These are targets, not measured guarantees. Provider plan retention and point-in-time recovery vary; verify contracted capabilities.

1. Assign a backup owner and authorized alternate. Configure automated managed database backups; agree on at least 30 days retention where lawful and affordable. Set alerts for failed backups and retention gaps. Include uploaded authorized evidence/object storage if that feature is added.
2. Use provider encryption and encrypted export storage with restricted service identities and separate credentials. Avoid unencrypted local health-data exports. Keep recovery credentials outside the application repository. Store backup metadata without client identifiers.
3. Before deployment, restore a backup into an isolated staging recovery database. Restrict network access. Do not connect ordinary development accounts or analytics tools to restored client data.
4. Run Alembic status, database integrity checks, organization counts, report counts and audit-chain reconciliation against the backup inventory. Test sign-in, organization isolation, role restrictions and approved-report immutability. Validate a sample of authorized records with the designated data custodian.
5. Record backup time, restore start/finish, actual data loss window, measured RPO/RTO, validation failures, approver and incident/change reference. Repeat quarterly and after material schema/provider changes.
6. For incidents, pause writes and background processing, preserve incident logs, confirm the approved recovery point, restore, reconfigure backend DATABASE_URL securely, and perform acceptance checks before reopening access. Communicate the recovered data window and reconcile records entered after the recovery point.
7. Retain incident evidence per policy; securely remove temporary restore databases after custodian approval. Never overwrite the sole available backup.

Example operator command for encrypted backups: pipe `pg_dump --format=custom "$DATABASE_URL"` directly to the organization's approved encryption tool and restricted storage service. Do not log the connection string. The exact tool, key custody and destination must be approved and tested in the deployment environment.
