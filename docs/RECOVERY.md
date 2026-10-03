# Backup and recovery runbook

Live backups remain unverified. The PostgreSQL CI exercise restores an encrypted dump into a separate disposable database, checks migration/master data and rejects tampering. This tests the procedure with master data, not live backup protection.

Proposed daily-policy objectives: RPO ≤24 hours; RTO ≤8 hours. These are targets, not guarantees. Assign a backup owner and alternate. Configure automated daily backups, restricted encrypted storage, failure alerts and approved retention (proposed 30 days). Verify provider-plan capabilities. Retain encryption keys separately from backup files.

## Encrypted backup

Install a PostgreSQL client at least as new as the server (hosted Neon: PostgreSQL 18). Supply DATABASE_URL and BACKUP_ENCRYPTION_KEY through a protected operator environment. The backup key is URL-safe base64 encoding of 32 random bytes. Never log keys or credentials.

```sh
python scripts/backup_database.py --output /restricted-storage/nutritrack-backup.enc
```

The script streams pg_dump into authenticated AES-GCM encryption, refuses overwrites and restricts file permissions. The scheduler/storage destination must be configured; application deployment does not silently enable it. Database-stored evidence and generated reports require the persistent EVIDENCE_ENCRYPTION_KEY after recovery.

## Isolated recovery

Create an empty restricted recovery database. Set RESTORE_DATABASE_URL to that recovery target and retain the original backup key. Never select the sole live database for a test.

```sh
python scripts/restore_database.py --input /restricted-storage/nutritrack-backup.enc --allow-restore
```

Authentication completes before pg_restore. Temporary plaintext is restricted and removed afterwards; the script does not erase an existing schema. Validate migration, organization/facility/report counts, audit inventory, sign-in, scope denial, report locks and evidence decryption. Record backup time, restore start/finish, actual loss window, measured RPO/RTO, failures and custodian approval. Repeat quarterly and after material changes.

For incidents: pause writes and jobs, preserve logs, authorize a recovery point, restore separately, validate, securely change the API database URL and reopen after acceptance. Reconcile records entered after the restored point. Remove temporary recovery resources under the approved retention procedure.
