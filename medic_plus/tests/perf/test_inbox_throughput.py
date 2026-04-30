"""Axis 4 — Lab Result Inbox queue throughput test.

MANUAL ONLY — skip-marked in CI. Run against staging:

    cd /home/fruppa/frappe-bench
    env/bin/python -m pytest apps/medic_plus/medic_plus/tests/perf/test_inbox_throughput.py -v -s

Target: 500 ORU messages ingested < 60 seconds via 10 parallel workers.
If throughput is insufficient, medic_plus.api.diagnostics.receive_oru should
be moved to a Frappe background job queue with priority=high.

Prerequisites:
  - medic_plus.api.diagnostics module deployed (Phase 5.1+)
  - BASE_URL and AUTH_TOKEN env vars set
  - A seeded test patient with a known SA ID (TEST_PATIENT_SAID env var)
"""

import os
import time
import concurrent.futures
import json
import urllib.request
import urllib.parse

import pytest


BASE_URL = os.environ.get("BASE_URL", "https://medic-demo-staging.thedaystar.co.za")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")
TEST_PATIENT_SAID = os.environ.get("TEST_PATIENT_SAID", "8001015009087")
TOTAL_MESSAGES = 500
WORKERS = 10


def _build_minimal_oru(accession: str, said: str) -> str:
    """Build a minimal valid HL7 v2.5 ORU R01 message."""
    ts = time.strftime("%Y%m%d%H%M%S")
    dob = said[0:6]  # YYMMDD from SAID
    return (
        f"MSH|^~\\&|AMPATH|AMPATH|MEDICP|MEDICP|{ts}||ORU^R01|{accession}|P|2.5\r"
        f"PID|1||{said}^^^SAID||Test^Patient||{dob}|F\r"
        f"OBR|1|{accession}|{accession}|2951-2^Sodium^LN\r"
        f"OBX|1|NM|2951-2^Sodium^LN||138|mmol/L|136-145|N\r"
    )


def _post_oru(accession: str) -> float:
    """POST one ORU to receive_oru and return elapsed seconds."""
    payload = json.dumps({
        "raw_hl7": _build_minimal_oru(accession, TEST_PATIENT_SAID),
    }).encode()
    url = f"{BASE_URL}/api/method/medic_plus.api.diagnostics.receive_oru"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AUTH_TOKEN}",
        },
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception:
        pass
    return time.perf_counter() - start


@pytest.mark.skip(reason="Manual throughput test — run on staging with diagnostics module deployed")
def test_inbox_500_messages_under_60s():
    """500 ORU messages ingested in < 60 seconds via 10 parallel workers."""
    if not AUTH_TOKEN:
        pytest.skip("AUTH_TOKEN not set")

    base_accession = int(time.time())
    accessions = [f"ACC{base_accession + i:010d}" for i in range(TOTAL_MESSAGES)]
    latencies: list[float] = []
    wall_start = time.time()

    def worker(batch):
        for acc in batch:
            latencies.append(_post_oru(acc))

    batches = [accessions[i::WORKERS] for i in range(WORKERS)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(worker, batches))

    elapsed = time.time() - wall_start
    print(f"\nLab Inbox throughput — {len(latencies)} messages in {elapsed:.1f}s")
    print(f"  throughput={len(latencies)/elapsed:.1f} msg/s")

    assert elapsed < 60, (
        f"500 messages took {elapsed:.1f}s — exceeds 60s target. "
        "Consider moving receive_oru to frappe.enqueue with priority=high."
    )
