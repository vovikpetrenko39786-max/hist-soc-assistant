# Railway safe deployment gate

This release must not be deployed until every gate below is complete. Keep all
secret values in Railway or a password manager; never commit or paste them into
issues, pull requests, logs, or chat.

## 1. Back up and inventory existing data

1. Create a restorable PostgreSQL backup using the Railway owner account.
2. Create a restorable snapshot or copy of the volume mounted at
   `RAILWAY_VOLUME_MOUNT_PATH`. The volume currently also stores textbooks, so
   preserve its complete contents.
3. Restore both backups into a separate non-production environment and verify
   that representative database rows and files are readable.
4. In the secured backend runtime, run `python -m scripts.audit_generated_exports`.
   Record only its aggregate counts in the deployment ticket. Investigate every
   missing, corrupt, unreadable, or outside-root record before migration.
5. Set the following backend attestations to `true` only after the corresponding
   work has actually been completed:
   `EXPORT_INVENTORY_CONFIRMED`, `EXPORT_BACKUP_CONFIRMED`, and
   `OUTPUT_STORAGE_MIGRATION_CONFIRMED`.

These flags are deployment gates, not backups and not proof of recoverability.

## 2. Configure authentication consistently

Generate a new high-entropy `PILOT_API_KEY` of at least 43 characters with a
password manager or cryptographic secret generator. Set the identical value in
the backend and Telegram services. Configure a different strong
`ADMIN_API_KEY` in the backend.

Set identical `TELEGRAM_ALLOWED_USER_IDS` and
`TELEGRAM_COURSE_BINDINGS_JSON` values in both services. Review every Telegram
ID, course UUID, and `source_key` against the test database. Removing a user
from either allowlist blocks access after restart. A course UUID grants access
to that course's memory, so treat the bindings as authorization configuration.

The bot sends `X-Pilot-User-ID`; the backend accepts it only with the shared
pilot key and verifies it against its own allowlist and course bindings. Do not
expose the backend directly to end users.

## 3. Preserve old documents and select durable output storage

Choose an absolute `OUTPUT_STORAGE_DIR` inside `RAILWAY_VOLUME_MOUNT_PATH`.
Keep textbook files and generated outputs in separate subdirectories. Verify
free capacity and set `OUTPUT_MIN_FREE_MB` with enough reserve for textbooks.

Copy old generated files only after the inventory and backups. Preserve paths
recorded in `exported_files`, or update them through a separately reviewed,
transactional migration. If old files remain in another directory on the same
volume, list that directory in `OUTPUT_LEGACY_STORAGE_ROOTS_JSON`; legacy roots
are read-only and must remain inside the declared volume. Never use `/` or an
ephemeral path as a legacy root.

## 4. Run preflight without leaking values

Create temporary owner-readable backend and bot environment snapshots outside
the repository, containing only the settings needed by the checker. Run:

```bash
python release_preflight.py --api-env /secure/backend.env --bot-env /secure/bot.env
```

Delete the temporary snapshots securely after the check. Preflight must report
zero blockers. It checks consistency and explicit confirmations; it does not
contact Railway or prove that backups can be restored.

## 5. Staged deployment and rollback

Deploy the backend and bot from the same reviewed commit in a controlled
maintenance window. Immediately verify public `/health`, authenticated bot
requests, denial for a non-allowlisted ID, denial of another user's course,
strict textbook behavior, next-lesson memory, DOCX/PDF download, and persistence
after restarting both services.

If any check fails, roll both services back to the previous commit and previous
environment-variable set. Do not delete or rewrite files during rollback. Use
the verified backups and inventory if a storage migration must be reversed.
