"""Performance instrumentation — RPC call-count and cache-hit tracking.

Lightweight Redis-based counters that add < 1 ms overhead per call.
All counter writes are fire-and-forget: any Redis failure is swallowed
so instrumentation never breaks a live request.

Public surface:
  track_call(method_name)       — call on RPC entry (always)
  track_cache_hit(method_name)  — call when a cached result is returned
  get_cache_stats()             — whitelisted; returns per-method stats
"""

import frappe

# The five highest-traffic whitelisted methods — tracked for hit-rate audit
TRACKED_METHODS = [
    "get_medical_records",
    "build_patient_summary",
    "search_icd10",
    "get_inpatient_summary",
    "build_dashboard",
]

_KEY_CALLS = "medic_plus:rpc_calls"
_KEY_HITS = "medic_plus:rpc_cache_hits"


def track_call(method_name: str) -> None:
    """Increment the RPC call counter for *method_name*. Never raises."""
    try:
        frappe.cache().hincrby(_KEY_CALLS, method_name, 1)
    except Exception:
        pass


def track_cache_hit(method_name: str) -> None:
    """Increment the cache-hit counter for *method_name*. Never raises."""
    try:
        frappe.cache().hincrby(_KEY_HITS, method_name, 1)
    except Exception:
        pass


@frappe.whitelist()
def get_cache_stats() -> list[dict]:
    """Return per-method call count, hit count, and hit-rate percentage.

    Restricted to Healthcare Administrator.
    """
    if "Healthcare Administrator" not in frappe.get_roles():
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    try:
        calls_map = frappe.cache().hgetall(_KEY_CALLS) or {}
        hits_map = frappe.cache().hgetall(_KEY_HITS) or {}
    except Exception:
        return []

    def _int(v) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    all_methods = set(TRACKED_METHODS) | set(calls_map.keys()) | set(hits_map.keys())
    result = []
    for method in sorted(all_methods):
        call_count = _int(calls_map.get(method) or calls_map.get(method.encode()))
        hit_count = _int(hits_map.get(method) or hits_map.get(method.encode()))
        hit_rate = (hit_count / call_count) if call_count > 0 else 0.0
        result.append({
            "method": method,
            "call_count": call_count,
            "hit_count": hit_count,
            "hit_rate": round(hit_rate, 4),
        })

    return result
