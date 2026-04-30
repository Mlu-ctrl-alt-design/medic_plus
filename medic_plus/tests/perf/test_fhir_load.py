"""Axis 3 — FHIR endpoint p95/p99 load test.

MANUAL ONLY — skip-marked in CI. Run against staging:

    cd /home/fruppa/frappe-bench
    env/bin/python -m pytest apps/medic_plus/medic_plus/tests/perf/test_fhir_load.py -v -s

Target: p95 < 500 ms, p99 < 1 s at 50 concurrent users on staging hardware.
Results must be recorded in the PR description before merging.

Prerequisites:
  - medic_plus.api.fhir module deployed (Phase 2+)
  - At least 10 test Patient records with custom_practice set
  - BASE_URL and AUTH_TOKEN env vars set
"""

import os
import statistics
import time
import concurrent.futures

import pytest


BASE_URL = os.environ.get("BASE_URL", "https://medic-demo-staging.thedaystar.co.za")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")
CONCURRENCY = 50
DURATION_S = 30


def _get_patient_ids() -> list[str]:
    """Return test patient IDs from the env or a static fixture list."""
    ids_env = os.environ.get("FHIR_TEST_PATIENTS", "")
    if ids_env:
        return ids_env.split(",")
    return [f"PAT-{i:05d}" for i in range(1, 11)]


def _fetch_fhir_patient(session, patient_id: str) -> float:
    """GET /api/fhir/R4/Patient/{id} and return elapsed seconds."""
    import urllib.request
    url = f"{BASE_URL}/api/fhir/R4/Patient/{patient_id}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            r.read()
    except Exception:
        pass
    return time.perf_counter() - start


@pytest.mark.skip(reason="Manual load test — run on staging with FHIR module deployed")
def test_fhir_patient_p95_under_500ms():
    """p95 latency for GET /api/fhir/R4/Patient/{id} is < 500 ms @ 50 concurrent users."""
    if not AUTH_TOKEN:
        pytest.skip("AUTH_TOKEN not set")

    patient_ids = _get_patient_ids()
    latencies: list[float] = []
    deadline = time.time() + DURATION_S

    def worker(_):
        import itertools
        for pid in itertools.cycle(patient_ids):
            if time.time() >= deadline:
                break
            latencies.append(_fetch_fhir_patient(None, pid))

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        list(pool.map(worker, range(CONCURRENCY)))

    assert latencies, "No requests completed"
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    mean = statistics.mean(latencies)

    print(f"\nFHIR Patient GET — {len(latencies)} requests @ {CONCURRENCY} concurrency")
    print(f"  mean={mean*1000:.0f}ms  p95={p95*1000:.0f}ms  p99={p99*1000:.0f}ms")

    assert p95 < 0.5, f"p95={p95*1000:.0f}ms exceeds 500ms target"
    assert p99 < 1.0, f"p99={p99*1000:.0f}ms exceeds 1000ms target"


@pytest.mark.skip(reason="Manual load test — run on staging with FHIR module deployed")
def test_fhir_everything_bundle_p95():
    """p95 for GET /api/fhir/R4/Patient/{id}/$everything is < 2 s @ 20 concurrent users."""
    if not AUTH_TOKEN:
        pytest.skip("AUTH_TOKEN not set")
    # Same structure as above but lower concurrency and relaxed target for $everything
    pytest.skip("Not yet implemented — requires $everything endpoint to be live")
