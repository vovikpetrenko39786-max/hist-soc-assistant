# Windows backup checklist (Railway, without Pro)

**Status:** operator runbook; it does not create backups by itself. Do not merge/deploy until the recovery drill in [RAILWAY_SAFE_DEPLOYMENT.md](RAILWAY_SAFE_DEPLOYMENT.md) succeeds. Never paste database URLs, passwords, tokens, or bucket credentials into GitHub, tickets, screenshots, or chat.

## Scope

The production project currently has **two independent PostgreSQL services** (`Postgres` and `pgvector`), each with a separate volume. Confirm which database is used by the backend, and back up **both** if their roles are not proven. Also preserve the backend volume `textbook-live-files` (mounted at `/app/data/source_files`) and the bucket `textbook-originals`. Do not assume a database dump includes source files, or that a volume snapshot includes the bucket.

## 1. Prepare Windows safely

Install the Railway CLI using the official instructions: https://docs.railway.com/cli . For the npm method, install a current Node.js LTS, open a new PowerShell window, and run:

```powershell
node --version
npm --version
npm install -g @railway/cli
railway --version
railway login
```

Create a local folder **outside the Git repository**, preferably on a drive with enough free space:

```powershell
$BackupRoot = Join-Path $HOME ("HistSoc-backup-" + (Get-Date -Format "yyyy-MM-dd-HHmm"))
New-Item -ItemType Directory -Path $BackupRoot | Out-Null
Write-Host $BackupRoot
```

Use `railway link` to select project `jubilant-warmth` and the **production** environment. Verify the selected project/service before any command. Avoid `railway up`, `railway deploy`, `railway volume delete`, `railway volume files upload`, and `railway postgres ... restore`.

## 2. Export PostgreSQL (read-only source)

Install the PostgreSQL client tools (including `pg_dump` and `pg_restore`) for Windows. In Railway's database service, find the external TCP connection settings; `*.railway.internal` addresses do not work from Windows. If external access is disabled, first investigate the documented `railway connect <service> --tunnel-only` option rather than exposing a database to the internet. Do not put passwords in PowerShell command history or saved scripts.

For **each** database, use the client connection fields in environment variables in the current PowerShell session and prompt for the password interactively. Example (replace placeholders in the session only; never commit values):

```powershell
$env:PGHOST = "<external-host-or-local-tunnel>"
$env:PGPORT = "<port>"
$env:PGUSER = "<username>"
$env:PGDATABASE = "<database>"
$env:PGSSLMODE = "require"
pg_dump --format=custom --no-owner --no-acl --file (Join-Path $BackupRoot "postgres.dump")
```

If using a local tunnel, check the appropriate SSL mode; a tunnel may not require the same TLS settings as the public endpoint. For the second database, change the target filename (for example `pgvector.dump`) and connection fields. Do not set `PGPASSWORD` in a command that may be logged. Use the interactive password prompt or a secure credential mechanism. The dump process reads the source but may place I/O load on it; schedule during a quiet period.

Verify both files exist, are nonempty, and have readable archive metadata:

```powershell
Get-ChildItem $BackupRoot -Filter *.dump | Select-Object Name,Length
pg_restore --list (Join-Path $BackupRoot "postgres.dump") | Select-Object -First 15
Get-FileHash (Join-Path $BackupRoot "postgres.dump") -Algorithm SHA256
```

Repeat archive inspection and hash calculation for the other dump. This is **not** proof of a successful restore.

## 3. Copy the backend volume (read-only)

Use the Railway CLI volume commands documented at https://docs.railway.com/cli/volume . First select the **backend service** and the correct volume; inspect the directory structure:

```powershell
railway volume list
railway volume files list /
```

The exact root shown by the CLI may differ from the mount path in the container. Verify it before downloading. The CLI supports downloading files **or directories**. Download the relevant source-files directory into a separate local destination, using the path confirmed by the listing:

```powershell
railway volume files download <verified-remote-directory> <local-backup-directory>
```

If the command rejects a directory or the installed CLI has different flags, consult `railway volume files download --help` and stop rather than using destructive commands. Preserve file names, sizes, and a file manifest. Do not modify or delete anything on the remote volume.

## 4. Copy the originals bucket

The `textbook-originals` bucket is **separate** from the backend volume. Use an S3-compatible client (for example AWS CLI) and credentials obtained privately from Railway's bucket settings. Verify endpoint, bucket name, and region from the Railway dashboard. The S3 command `aws s3 sync s3://<bucket-name> <local-folder> --endpoint-url <bucket-endpoint>` downloads objects when the S3 bucket is the source and the local folder is the destination. **Never reverse the direction**. First list objects, and verify the object count and total bytes after the download. Keep credentials in a protected local profile, not in a repository or transcript.

## 5. Recovery drill and release gate

- Store an encrypted second copy on a separate disk or protected cloud storage; keep the decryption key separately.
- Verify SHA-256 manifests and spot-check representative source files and bucket objects.
- Restore the PostgreSQL dumps into a **new, isolated non-production** database using `pg_restore`; compare table counts and representative records. Never restore into the existing production database.
- Verify source-file and bucket object retrieval independently. Check the legacy-export inventory using the read-only audit script described in the release runbook.
- Record completion date, operator, backup locations, verification results, and recovery outcome **without secrets or student data**.
- Set `EXPORT_BACKUP_CONFIRMED=true`, `EXPORT_INVENTORY_CONFIRMED=true`, and `OUTPUT_STORAGE_MIGRATION_CONFIRMED=true` **only after** their respective requirements are actually satisfied. These switches do not create backups.

**Stop condition:** if any source is inaccessible, a dump fails, a directory is missing, or the restore drill fails, leave the PR unmerged and production unchanged.
