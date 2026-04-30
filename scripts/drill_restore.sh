#!/usr/bin/env bash
# drill_restore.sh — Periodic backup-and-restore drill for Medic Plus.
#
# Usage:
#   ./scripts/drill_restore.sh [BACKUP_FILE] [RESTORE_SITE]
#
# Arguments:
#   BACKUP_FILE   Path to the .tar.gz backup produced by bench backup.
#                 Defaults to the most recent backup in ~/frappe-bench/sites/*/private/backups/
#   RESTORE_SITE  Frappe site name to restore into (must be a disposable drill site).
#                 Defaults to "drill-$(date +%Y%m%d).localhost"
#
# Environment variables:
#   BENCH_PATH    Path to the frappe-bench directory (default: ~/frappe-bench)
#   LOG_SITE      The live site to log the drill result into.
#                 Default: medic-demo-staging.thedaystar.co.za
#   RUN_BY        Frappe user who ran the drill (default: Administrator)
#
# On success: logs a Backup Drill Log row on LOG_SITE and exits 0.
# On failure: logs the failure (smoke_pass=0) and exits 1.

set -euo pipefail

BENCH_PATH="${BENCH_PATH:-$HOME/frappe-bench}"
LOG_SITE="${LOG_SITE:-medic-demo-staging.thedaystar.co.za}"
RUN_BY="${RUN_BY:-Administrator}"

# ---------------------------------------------------------------------------
# Resolve backup file
# ---------------------------------------------------------------------------
if [[ -n "${1:-}" ]]; then
    BACKUP_FILE="$1"
else
    BACKUP_FILE=$(find "$BENCH_PATH/sites" -name "*.tar.gz" -path "*/private/backups/*" \
        | sort -r | head -1)
fi

if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: No backup file found. Pass a path as the first argument." >&2
    exit 1
fi

BACKUP_SIZE_MB=$(du -m "$BACKUP_FILE" | cut -f1)
BACKUP_FILENAME=$(basename "$BACKUP_FILE")

# ---------------------------------------------------------------------------
# Resolve drill site name
# ---------------------------------------------------------------------------
DRILL_SITE="${2:-drill-$(date +%Y%m%d).localhost}"

echo "=== Medic Plus Backup-Restore Drill ==="
echo "Backup file : $BACKUP_FILE ($BACKUP_SIZE_MB MB)"
echo "Restore site: $DRILL_SITE"
echo "Log site    : $LOG_SITE"
echo "========================================"

# ---------------------------------------------------------------------------
# Create a fresh drill site
# ---------------------------------------------------------------------------
cd "$BENCH_PATH"

echo "[1/5] Creating drill site: $DRILL_SITE ..."
bench new-site "$DRILL_SITE" \
    --admin-password "DrillP@ssw0rd" \
    --db-name "drill_$(date +%Y%m%d)" \
    --no-mariadb-socket \
    2>&1 | tail -5

echo "[2/5] Restoring backup ..."
RESTORE_START=$(date +%s)
bench --site "$DRILL_SITE" restore "$BACKUP_FILE" \
    --admin-password "DrillP@ssw0rd" \
    2>&1 | tail -10
RESTORE_END=$(date +%s)
RESTORE_ELAPSED=$((RESTORE_END - RESTORE_START))
echo "Restore elapsed: ${RESTORE_ELAPSED}s"

# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------
echo "[3/5] Running smoke tests ..."

SMOKE_PASS=1
PATIENT_COUNT=0
PRACTICE_COUNT=0

PATIENT_COUNT=$(bench --site "$DRILL_SITE" execute frappe.db.count \
    --args '["Patient"]' 2>/dev/null || echo 0)

PRACTICE_COUNT=$(bench --site "$DRILL_SITE" execute frappe.db.count \
    --args '["Practice"]' 2>/dev/null || echo 0)

# Basic smoke: at least one patient and one practice must be present
if [[ "$PATIENT_COUNT" -lt 1 || "$PRACTICE_COUNT" -lt 1 ]]; then
    echo "WARN: Smoke test FAILED — patient_count=$PATIENT_COUNT practice_count=$PRACTICE_COUNT"
    SMOKE_PASS=0
else
    echo "Smoke test PASSED — patient_count=$PATIENT_COUNT practice_count=$PRACTICE_COUNT"
fi

# ---------------------------------------------------------------------------
# Log result to the live LOG_SITE
# ---------------------------------------------------------------------------
echo "[4/5] Logging drill result to $LOG_SITE ..."

NOTES="Automated drill. Restore site: $DRILL_SITE. Elapsed: ${RESTORE_ELAPSED}s."

bench --site "$LOG_SITE" execute medic_plus.api.backup_drill._log_drill_result \
    --kwargs "{
        \"drill_date\": \"$(date +%Y-%m-%d)\",
        \"backup_file_name\": \"$BACKUP_FILENAME\",
        \"backup_size_mb\": $BACKUP_SIZE_MB,
        \"restore_elapsed_s\": $RESTORE_ELAPSED,
        \"smoke_pass\": $SMOKE_PASS,
        \"patient_count_restored\": $PATIENT_COUNT,
        \"practice_count_restored\": $PRACTICE_COUNT,
        \"run_by\": \"$RUN_BY\",
        \"notes\": \"$NOTES\"
    }" 2>&1

# ---------------------------------------------------------------------------
# Tear down drill site
# ---------------------------------------------------------------------------
echo "[5/5] Dropping drill site: $DRILL_SITE ..."
bench drop-site "$DRILL_SITE" --force --no-backup 2>&1 | tail -3

echo "=== Drill complete. Smoke pass: $SMOKE_PASS ==="

if [[ "$SMOKE_PASS" -eq 0 ]]; then
    exit 1
fi
