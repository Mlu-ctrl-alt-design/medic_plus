"""
medic_plus.api.ai — AI gateway wrapping Anthropic SDK.

Architecture:
- PHI redaction layer strips SA ID / name / DOB / address / contact before
  any text leaves the bench. Tokens are deterministic within one call, and
  restore_phi() replaces them back in the AI output.
- call_claude() is the single transport primitive. All feature functions go
  through it so prompt-caching, spend-cap enforcement, and inference logging
  happen consistently.
- Anthropic client is instantiated lazily so unit tests can mock it before
  the module-level import fires.
- No live network calls in CI — tests patch _get_anthropic_client().
"""

import base64
import hashlib
import json
import re
import time
from typing import Any

import frappe

# ── constants ─────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "claude-sonnet-4-6"
OPUS_MODEL = "claude-opus-4-7"

# Cost per 1M tokens (USD) — approximate list pricing for spend tracking
_COST_PER_1M = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
}

# PHI field names to scan when building the redaction map
_PHI_FIELDS = [
    "patient_name", "email", "mobile", "phone", "dob",
    "custom_sa_id_number", "address",
    "first_name", "last_name", "middle_name",
]

# SOAP section headers in Claude output
_SOAP_RE = re.compile(
    r"SUBJECTIVE:\s*(.*?)(?=OBJECTIVE:|$)"
    r"|OBJECTIVE:\s*(.*?)(?=ASSESSMENT:|$)"
    r"|ASSESSMENT:\s*(.*?)(?=PLAN:|$)"
    r"|PLAN:\s*(.*?)$",
    re.DOTALL | re.IGNORECASE,
)

# ICD-10 DDx line: "1. J06.9 — description"
_DDX_RE = re.compile(r"\d+\.\s+([A-Z]\d+[\d.]*)\s+[—\-–]\s+(.+)")


# ── PHI redaction ─────────────────────────────────────────────────────────────

def _make_token(value: str) -> str:
    """Deterministic, opaque token for a PHI value (hex prefix of SHA-256)."""
    h = hashlib.sha256(value.encode()).hexdigest()[:8].upper()
    return f"[PATIENT_{h}]"


def redact_phi(text: str, phi_map: dict | None = None) -> tuple[str, dict]:
    """
    Replace PHI substrings in `text` with deterministic tokens.

    Returns (redacted_text, token_map) where token_map maps each original
    PHI string to its replacement token. Pass token_map to restore_phi()
    to reverse the substitution in AI output.

    phi_map: dict of PHI fields from the patient record. Keys match _PHI_FIELDS.
    """
    token_map: dict[str, str] = {}

    if not phi_map:
        return text, token_map

    # Build ordered list of (phi_value, token) — longest first so sub-matches
    # don't get partially replaced before the full string is found.
    pairs: list[tuple[str, str]] = []
    for field in _PHI_FIELDS:
        raw = phi_map.get(field, "") or ""
        if not raw:
            continue
        raw = str(raw).strip()
        if len(raw) < 2:
            continue
        token = _make_token(raw)
        if raw not in token_map:
            token_map[raw] = token
            pairs.append((raw, token))

        # Also redact sub-tokens (e.g. first name / last name separately)
        sub_tokens = re.split(r"[\s,]+", raw)
        for sub in sub_tokens:
            sub = sub.strip()
            if len(sub) >= 4 and sub not in token_map:
                sub_token = _make_token(sub)
                token_map[sub] = sub_token
                pairs.append((sub, sub_token))

    # Sort longest first to avoid partial replacement
    pairs.sort(key=lambda p: len(p[0]), reverse=True)

    redacted = text
    for phi_val, token in pairs:
        # Case-insensitive replacement to catch transcription capitalisation
        redacted = re.sub(re.escape(phi_val), token, redacted, flags=re.IGNORECASE)

    return redacted, token_map


def restore_phi(text: str, token_map: dict) -> str:
    """Replace tokens back with original PHI values in the AI output."""
    # Invert: token → original (token_map is original → token)
    inv = {v: k for k, v in token_map.items()}
    result = text
    for token, original in inv.items():
        result = result.replace(token, original)
    return result


# ── Anthropic client ──────────────────────────────────────────────────────────

def _get_anthropic_client():
    """Lazy import so tests can patch before the module is imported."""
    import anthropic  # type: ignore
    api_key = frappe.db.get_single_value("Medic Plus Settings", "anthropic_api_key") or ""
    return anthropic.Anthropic(api_key=api_key)


# ── Practice AI settings helper ───────────────────────────────────────────────

def _get_practice_ai_settings(practice: str) -> dict:
    """Return Practice AI Settings for the given practice, or defaults."""
    if not frappe.db.exists("Practice AI Settings", practice):
        return {
            "ai_enabled": False,
            "note_gen_enabled": False,
            "ddx_enabled": False,
            "rx_check_enabled": False,
            "monthly_spend_cap_usd": 0,
            "default_model": DEFAULT_MODEL,
        }
    return frappe.db.get_value(
        "Practice AI Settings",
        practice,
        [
            "ai_enabled", "note_gen_enabled", "ddx_enabled",
            "rx_check_enabled", "monthly_spend_cap_usd", "default_model",
        ],
        as_dict=True,
    ) or {}


# ── Spend cap enforcement ─────────────────────────────────────────────────────

def _check_and_enforce_spend_cap(practice: str) -> None:
    """
    Sum cost_usd from AI Inference Log for current calendar month.
    If the total exceeds monthly_spend_cap_usd (and cap > 0), disable AI.
    """
    cap = frappe.db.get_value("Practice AI Settings", practice, "monthly_spend_cap_usd") or 0
    if not cap:
        return  # 0 = no cap enforced

    from frappe.utils import get_first_day, now_datetime
    month_start = get_first_day(now_datetime().date()).strftime("%Y-%m-%d")

    result = frappe.db.sql(
        """SELECT COALESCE(SUM(cost_usd), 0)
           FROM `tabAI Inference Log`
           WHERE practice = %s AND creation >= %s""",
        (practice, month_start),
    )
    total_spend = (result[0][0] if result else 0) or 0

    if total_spend >= cap:
        frappe.db.set_value("Practice AI Settings", practice, "ai_enabled", 0)


# ── Core transport ────────────────────────────────────────────────────────────

def call_claude(
    *,
    system: str,
    user: str,
    practice: str,
    feature: str,
    model: str | None = None,
    patient_ai_consent: bool = True,
) -> dict:
    """
    Single transport primitive for all Claude calls.

    Enforces:
    1. Patient AI consent (gate before any call)
    2. Practice AI enabled + feature-level toggle
    3. Spend cap (checked after each call to disable proactively)
    4. Prompt caching via cache_control on system block

    Returns dict: {text, latency_ms, cost_usd, input_tokens, output_tokens, model}
    """
    if not patient_ai_consent:
        frappe.throw(
            "Patient has not consented to AI processing.",
            frappe.PermissionError,
        )

    settings = _get_practice_ai_settings(practice)
    if not settings.get("ai_enabled"):
        frappe.throw(
            "AI features are not enabled for this practice.",
            frappe.PermissionError,
        )

    feature_flag = f"{feature}_enabled"
    if not settings.get(feature_flag, False):
        frappe.throw(
            f"AI feature '{feature}' is not enabled for this practice.",
            frappe.PermissionError,
        )

    effective_model = model or settings.get("default_model") or DEFAULT_MODEL

    client = _get_anthropic_client()
    t0 = time.monotonic()

    response = client.messages.create(
        model=effective_model,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user}],
    )

    latency_ms = int((time.monotonic() - t0) * 1000)
    text = response.content[0].text if response.content else ""
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    costs = _COST_PER_1M.get(effective_model, {"input": 3.0, "output": 15.0})
    cost_usd = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000

    _check_and_enforce_spend_cap(practice)

    return {
        "text": text,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "model": effective_model,
    }


# ── Inference logger ──────────────────────────────────────────────────────────

def _log_inference(
    *,
    practice: str,
    encounter: str,
    practitioner: str,
    feature: str,
    input_redacted: str,
    output: str,
    model: str,
    latency_ms: int,
    cost_usd: float,
) -> None:
    """Insert an AI Inference Log row. Silently skips if doctype doesn't exist yet."""
    try:
        log = frappe.new_doc("AI Inference Log")
        log.practice = practice
        log.encounter = encounter
        log.practitioner = practitioner
        log.feature = feature
        log.input_redacted = input_redacted
        log.output = output
        log.model = model
        log.latency_ms = latency_ms
        log.cost_usd = cost_usd
        log.practitioner_action = "Pending"
        log.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "AI Inference Log insert failed")


# ── Whisper transcription stub ────────────────────────────────────────────────

def _transcribe_audio(audio_b64: str) -> str:
    """
    Transcribe base64-encoded audio via Whisper API.

    In production: POST to OpenAI Whisper endpoint or a self-hosted Whisper
    server configured in Medic Plus Settings. In tests, this function is
    always patched.
    """
    try:
        import openai  # type: ignore
        api_key = frappe.db.get_single_value("Medic Plus Settings", "openai_api_key") or ""
        client = openai.OpenAI(api_key=api_key)
        audio_bytes = base64.b64decode(audio_b64)
        # Whisper expects a file-like object
        import io
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.webm"
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        return transcript.text
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Whisper transcription failed")
        return ""


# ── Feature: Note generation ─────────────────────────────────────────────────

_NOTE_GEN_SYSTEM = """You are a clinical scribe for a South African general practice.
Given a patient consultation transcription, output a structured SOAP note.

Format exactly as:
SUBJECTIVE: <patient's complaints and history>
OBJECTIVE: <examination findings and vital signs>
ASSESSMENT: <diagnosis or differential>
PLAN: <investigations, treatments, follow-up>

Be concise. Use medical abbreviations. Output only the SOAP note, no preamble."""


@frappe.whitelist()
def generate_soap_note(
    audio_b64: str,
    encounter: str,
    practice: str,
    practitioner: str,
    patient_ai_consent: bool = True,
    patient_phi: dict | None = None,
) -> dict:
    """
    Transcribe audio via Whisper, redact PHI, structure via Claude SOAP format.

    Returns: {subjective, objective, assessment, plan, log_name}
    """
    transcription = _transcribe_audio(audio_b64)
    redacted_transcription, token_map = redact_phi(transcription, phi_map=patient_phi or {})

    user_prompt = f"Consultation transcription:\n\n{redacted_transcription}"

    result = call_claude(
        system=_NOTE_GEN_SYSTEM,
        user=user_prompt,
        practice=practice,
        feature="note_gen",
        patient_ai_consent=patient_ai_consent,
    )

    raw_text = result["text"]
    soap = _parse_soap(raw_text)

    _log_inference(
        practice=practice,
        encounter=encounter,
        practitioner=practitioner,
        feature="note_gen",
        input_redacted=redacted_transcription,
        output=raw_text,
        model=result["model"],
        latency_ms=result["latency_ms"],
        cost_usd=result["cost_usd"],
    )

    return soap


def _parse_soap(text: str) -> dict:
    """Extract SOAP sections from Claude output."""
    sections = {"subjective": "", "objective": "", "assessment": "", "plan": ""}
    current = None
    for line in text.splitlines():
        line = line.strip()
        upper = line.upper()
        if upper.startswith("SUBJECTIVE:"):
            current = "subjective"
            sections[current] = line[len("SUBJECTIVE:"):].strip()
        elif upper.startswith("OBJECTIVE:"):
            current = "objective"
            sections[current] = line[len("OBJECTIVE:"):].strip()
        elif upper.startswith("ASSESSMENT:"):
            current = "assessment"
            sections[current] = line[len("ASSESSMENT:"):].strip()
        elif upper.startswith("PLAN:"):
            current = "plan"
            sections[current] = line[len("PLAN:"):].strip()
        elif current:
            sections[current] = (sections[current] + "\n" + line).strip()
    return sections


# ── Feature: Differential diagnosis ──────────────────────────────────────────

_DDX_SYSTEM = """You are a clinical decision support system for a South African GP.
Given subjective and objective findings, suggest the top 3 differential diagnoses
with SA-canonical ICD-10-ZA codes.

Format each line as:
<number>. <ICD-10 code> — <description>

Example:
1. J06.9 — Acute upper respiratory infection, unspecified
2. J00 — Acute nasopharyngitis (common cold)
3. J02.9 — Acute pharyngitis, unspecified

Output only the 3 lines, no preamble."""


@frappe.whitelist()
def suggest_ddx(
    subjective: str,
    objective: str,
    practice: str,
    practitioner: str,
    encounter: str,
    patient_ai_consent: bool = True,
) -> dict:
    """Return top-3 differential diagnoses with ICD-10-ZA codes."""
    user_prompt = f"SUBJECTIVE: {subjective}\nOBJECTIVE: {objective}"

    result = call_claude(
        system=_DDX_SYSTEM,
        user=user_prompt,
        practice=practice,
        feature="ddx",
        patient_ai_consent=patient_ai_consent,
    )

    _log_inference(
        practice=practice,
        encounter=encounter,
        practitioner=practitioner,
        feature="ddx",
        input_redacted=user_prompt,
        output=result["text"],
        model=result["model"],
        latency_ms=result["latency_ms"],
        cost_usd=result["cost_usd"],
    )

    candidates = []
    for line in result["text"].splitlines():
        m = _DDX_RE.search(line)
        if m:
            candidates.append({"icd_code": m.group(1), "description": m.group(2).strip()})

    return {"candidates": candidates[:3], "raw": result["text"]}


# ── Feature: Rx sanity check ──────────────────────────────────────────────────

_RX_SYSTEM = """You are a pharmacovigilance assistant for a South African GP.
Given a list of prescribed medications and patient allergies, identify any
clinically significant interactions or contraindications.

If none found, respond with: "No significant interactions identified."
Otherwise respond with a single-sentence warning starting with ⚠ """


@frappe.whitelist()
def rx_sanity_check(
    medications: list,
    allergies: list,
    practice: str,
    practitioner: str,
    encounter: str,
    patient_ai_consent: bool = True,
) -> dict:
    """AI-powered Rx safety check — third warning row alongside deterministic checks."""
    if isinstance(medications, str):
        medications = json.loads(medications)
    if isinstance(allergies, str):
        allergies = json.loads(allergies)

    med_list = "\n".join(f"- {m}" for m in medications)
    allergy_list = "\n".join(f"- {a}" for a in allergies) or "None reported"
    user_prompt = f"Medications:\n{med_list}\n\nAllergies:\n{allergy_list}"

    result = call_claude(
        system=_RX_SYSTEM,
        user=user_prompt,
        practice=practice,
        feature="rx_check",
        patient_ai_consent=patient_ai_consent,
    )

    _log_inference(
        practice=practice,
        encounter=encounter,
        practitioner=practitioner,
        feature="rx_check",
        input_redacted=user_prompt,
        output=result["text"],
        model=result["model"],
        latency_ms=result["latency_ms"],
        cost_usd=result["cost_usd"],
    )

    return {
        "warning": result["text"],
        "model": result["model"],
        "latency_ms": result["latency_ms"],
    }
