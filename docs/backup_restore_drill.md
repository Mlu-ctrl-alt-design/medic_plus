# Backup and Restore Drill — Standard Operating Procedure

**Phase 5.11 | Medic Plus**
**Frequency:** Monthly (automated reminder fires on the 1st of each month)
**Threshold:** Drill must be completed within 35 days of the previous drill

---

## Purpose

This procedure verifies that the Medic Plus platform backup is restorable and
that patient data is recoverable to a known-good state. It satisfies the
POPIA requirement for tested data recovery capability and supports the practice
management disaster-recovery policy.

---

## Roles

| Role | Responsibility |
|------|----------------|
| Healthcare Administrator | Receives the monthly reminder email; runs the drill or delegates |
| Platform Engineer | Runs the drill script; logs the result |

---

## Prerequisites

1. Access to the Frappe bench server: `ssh fruppa@medic-demo-staging.thedaystar.co.za`
2. An existing `.tar.gz` backup in `~/frappe-bench/sites/*/private/backups/`
   — produced by the daily `bench backup` cron job.
3. A disposable MariaDB database slot (the drill script creates and drops it automatically).
4. The `medic_plus` app deployed with Phase 5.11 or later.

---

## Procedure

### Step 1 — SSH to the bench server

```bash
ssh fruppa@medic-demo-staging.thedaystar.co.za
cd ~/frappe-bench
```

### Step 2 — Run the drill script

```bash
apps/medic_plus/scripts/drill_restore.sh
```

The script will:
1. Locate the most recent backup automatically (or accept a path as `$1`).
2. Create a throw-away Frappe site `drill-YYYYMMDD.localhost`.
3. Restore the backup to that site.
4. Count `Patient` and `Practice` records as a smoke test.
5. Log a `Backup Drill Log` row on the live site with the results.
6. Drop the drill site.

**Optional overrides (environment variables):**

| Variable | Default | Purpose |
|----------|---------|---------|
| `BENCH_PATH` | `~/frappe-bench` | Path to the bench directory |
| `LOG_SITE` | `medic-demo-staging.thedaystar.co.za` | Site to log the result into |
| `RUN_BY` | `Administrator` | Frappe user attributed in the log |

Example with a specific backup file:

```bash
LOG_SITE=medic-demo-staging.thedaystar.co.za \
RUN_BY=admin@thedaystar.co.za \
apps/medic_plus/scripts/drill_restore.sh \
    sites/medic-demo-staging.thedaystar.co.za/private/backups/20260430_020001-medic_db.tar.gz
```

### Step 3 — Verify the log entry

Open the Frappe Desk on the live site:

```
https://medic-demo-staging.thedaystar.co.za/app/backup-drill-log
```

Confirm the new row shows:
- **Drill Date:** today's date
- **Smoke Test Passed:** ✓
- **Patient Count Restored:** > 0
- **Practice Count Restored:** > 0

### Step 4 — If the drill fails

If the script exits with code 1 (smoke test failure or restore error):

1. Read the output to identify the failure reason.
2. Check the backup file integrity: `tar -tzf <backup_file> | head`.
3. Investigate the MariaDB restore logs.
4. Fix the underlying issue before the next production backup runs.
5. Re-run the drill with the same (or a known-good) backup file.
6. The Backup Drill Log row with `smoke_pass = 0` is **not deleted** — it remains
   as an audit record. Run a successful drill to create a passing row.

---

## Automated Reminder

The monthly scheduler (`0 8 1 * *`) calls `medic_plus.api.backup_drill.send_drill_reminder`.
It sends an email to all active Healthcare Administrator accounts:

- **Subject contains `ACTION REQUIRED`** when:
  - No drill log row exists, or
  - The most recent drill was ≥ 35 days ago.
- **Subject is informational** (no ACTION REQUIRED) when the most recent drill
  was < 35 days ago.

---

## Append-Only Guarantee

`Backup Drill Log` records **cannot be deleted** by any role, including
Healthcare Administrator and System Manager. The `on_trash` hook raises a
`ValidationError`. This ensures the audit trail is tamper-evident.

---

## Related

- `medic_plus/api/backup_drill.py` — scheduler function + log helper
- `scripts/drill_restore.sh` — restore automation script
- `medic_plus/medic_plus/doctype/backup_drill_log/` — DocType definition
- `medic_plus/api/test_backup_drill.py` — integration tests
