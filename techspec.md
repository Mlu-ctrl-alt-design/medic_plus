# techspec.md — Medic Plus

Living technical specification. Every feature, bugfix, refactor, and design decision is logged here with dates.

---

## 2026-05-02 — Phase 1D (Issue #27): Medication Safety (Drug Master + Safety Checks + HPCSA Booklet 8)

### Scope

SA-compliant medication safety layer on top of the existing `Drug Prescription` child table
(Healthcare module) and `Patient Allergy` doctype.  Three warn-not-block checks fire on every
`Patient Encounter` `before_save` that carries a `custom_nappi_code_value`-tagged drug row.
HPCSA Booklet 8 print format added.  SPA prescription panel ships with live warning badges and
override UX.

### Blocker Status (Issue #27 blocked by #25 + #26)

| Issue | Expected | Actual |
|-------|----------|--------|
| #25 — Terminology stack (NAPPI / ATC) | Merged to develop | ✅ Merged (`53e787a`) |
| #26 — Structured SOAP encounter | Issue still open in GitHub | ✅ **Code merged** (`189977d`, `7833a27`) — issue tracker not updated |

The `patient_allergy` doctype and Healthcare module's native `drug_prescription` child table on
`Patient Encounter` provided all functional plumbing needed; full #26 SOAP fields (subjective /
assessment_code / plan) are present in develop and are referenced by the Booklet 8 print format.

### New Doctypes

#### Drug Master (`DM-.#####`)

Platform-level pharmaceutical catalogue keyed by NAPPI Code Value.

| Field | Type | Notes |
|-------|------|-------|
| `nappi_code_value` | Link → Code Value | Required; NAPPI system seed |
| `drug_name` | Data | Auto-filled from Code Value `display` on before_save |
| `nappi_code` | Data (read-only) | Parsed from Code Value name: `"719318-NAPPI"` → `"719318"` |
| `atc_code_value` | Link → Code Value | ATC system — drives allergy class matching |
| `atc_code` | Data (read-only) | Parsed from ATC CV name: `"J01MA-ATC"` → `"J01MA"` |
| `ingredient` | Data | INN / SNOMED stub |
| `schedule` | Select S0–S6 | SA SAHPRA schedule |
| `dosage_form` | Data | e.g. tablet, capsule, syrup |
| `strength` | Data | e.g. 500mg, 250mg/5ml |

Permissions: `System Manager` + `Healthcare Administrator` full CRUD; `Practice Admin` / `Practice Doctor` read.
No PQC — platform catalogue, visible to all authenticated practice users.

#### Prescription Override Reason (child table of `Patient Encounter`)

Captures practitioner's clinical justification for each dismissed safety warning.

| Field | Type |
|-------|------|
| `warning_type` | Select: Drug Allergy / Drug Interaction / Schedule Rule |
| `drug_name` | Data |
| `practitioner` | Link → Healthcare Practitioner |
| `dismissed_at` | Datetime |
| `reason` | Small Text (required) |

**PQC** (`get_prescription_override_reason_permission_query`): scopes via parent
`Patient Encounter.custom_practice` — identical pattern to `Patient Identifier` child-table PQC.

### Custom Fields Added (7)

| Doctype | Field | Type | Notes |
|---------|-------|------|-------|
| `Drug Prescription` | `custom_nappi_code_value` | Link → Code Value | NAPPI CV — entry point for safety checks |
| `Drug Prescription` | `custom_schedule` | Select S0–S6 | Auto-populated from Drug Master |
| `Drug Prescription` | `custom_repeats_authorised` | Int | Phase 5 dispensation hook decrements |
| `Drug Prescription` | `custom_repeats_remaining` | Int | Stub — decremented by dispensation event |
| `Drug Prescription` | `custom_generic_substitution_allowed` | Check | |
| `Patient Allergy` | `custom_atc_code` | Data | ATC class code for class-level allergy matching (e.g. `J01MA`) |
| `Patient Encounter` | `custom_prescription_override_reasons` | Table → Prescription Override Reason | |

### Code Values Added

| Name | System | Display |
|------|--------|---------|
| `719390-NAPPI` | NAPPI | Levofloxacin 500mg tablet |

### Safety Check Module (`api/drug_safety.py`)

Pure functions — no side effects, no Frappe session assumptions:

```
check_drug_allergy(patient, atc_code, drug_name) → list[dict]
  Matching: (1) allergy.custom_atc_code == atc_code  OR  (2) allergy.substance ⊆ drug_name (case-insensitive)
  Only Active, Drug-category allergies. Returns [] if patient absent.

check_drug_interaction(nappi_code_values) → list[dict]
  Cross-product check against Healthcare's Drug Interaction table.
  Resolves drug names via Drug Master. Skips cleanly when table is empty.

check_schedule_rule(nappi_code_value, prescriber) → list[dict]
  S5 rule: prescriber must have custom_practice_number (MP/PR number).
  S6 rule: no repeats permitted (always warned); + S5 MP rule.
  S0–S4: no warning.

run_safety_checks(encounter_doc) → list[dict]
  Aggregates all three checks for every drug_prescription row with custom_nappi_code_value.
  Attaches result to doc._drug_safety_warnings for test assertions.
```

Warning dict shape: `{ type, drug, message, severity | None }`.

### Before-save Hook (`run_prescription_safety`)

Registered in `hooks.py` as `Patient Encounter.before_save`.

1. Calls `run_safety_checks(doc)`.
2. Collects drugs whose names appear in `custom_prescription_override_reasons` rows → **covered**.
3. Calls `frappe.msgprint(uncovered_messages, indicator="orange", raise_exception=False)` — non-blocking.
4. Document saves regardless of warnings.

The SPA may surface warnings earlier (before save) via `check_prescription_safety` endpoint so the
user can fill in override reasons before the first save attempt.

### HPCSA Booklet 8 Print Format

Registered as `"Drug Prescription Booklet 8"` on `Patient Encounter`.

Sections (all from Medicines Act 101/1965 + HPCSA Booklet 8 requirements):
- **Letterhead**: practice name, address, phone, email, logo
- **HPCSA credentialing bar**: practitioner name + HPCSA number + MP/PR number
- **Rx title** with statutory subtitle
- **Patient bar**: name + DOB + SA ID + encounter date + reference
- **Drug table**: medicine name + NAPPI code + schedule badge (S5/S6 red) + strength + form + dosage + qty + repeats remaining + instructions
- **Override reasons** section (renders only when `custom_prescription_override_reasons` present)
- **Signature block**: handwritten signature image + HPCSA + MP/PR + date
- **Statutory disclaimer**: Medicines Act + S6 no-repeat rule

### Whitelisted SPA Endpoints (`api/daystar_health.py`)

| Endpoint | Purpose |
|----------|---------|
| `check_prescription_safety(patient, nappi_code_values)` | Aggregate allergy + schedule checks; cross-tenant guard via `get_active_practice()` |
| `get_drug_master_by_nappi(nappi_code_value)` | Single Drug Master lookup for SPA auto-fill (schedule, strength, dosage_form) |

### SPA Prescription Panel (`meridian-new-visit.jsx`)

`MPrescriptionPanel` (exported as `window.MPrescriptionPanel`):
- Controlled component: `rows`, `onChange`, `patient`, `prescriber`, `disabled` props
- `MPrescriptionRow` per drug: NAPPI picker (`MNappiPicker`), drug name, schedule (read-only), strength, dosage form, dosage, duration, repeats authorised, generic substitution checkbox
- Auto-fill: on NAPPI selection, calls `get_drug_master_by_nappi` to populate schedule/strength/dosage_form
- Live warning badges: on NAPPI change, calls `check_prescription_safety`; orange badge = uncovered warning; grey = override noted
- Override UX: warning badge click expands textarea; uncovered-warning notice shown when any warning lacks override reason
- Remove row button; empty state placeholder; "+ Add drug" button

### Tests

#### Python (`api/test_drug_safety.py`) — 16 IntegrationTestCase assertions

| Class | Assertions |
|-------|-----------|
| `TestDrugMasterAutoPopulate` | `nappi_code` + `atc_code` populated from Code Values on before_save |
| `TestCheckDrugAllergy` | ATC match warns; different ATC no warning; resolved allergy no warning; ingredient substring fallback |
| `TestEncounterSafetyWarning` | `run_safety_checks` returns allergy warning; encounter saves; warnings attached to doc |
| `TestPrescriptionOverrideReason` | Override row persists; covered warnings not re-surfaced |
| `TestPrescriptionCrossTenant` | Encounter PQC excludes Practice B; override reason PQC excludes Practice B; `frappe.get_all` returns nothing for Practice B user |
| `TestScheduleRuleCheck` | S5 + missing MP number warns; S6 always warns about no repeats; S4 no warning |

All classes have `IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]`.

#### Playwright UI (`tests/ui/test_prescription_panel_ui.py`) — 8 tests

| Class | Assertions |
|-------|-----------|
| `TestPrescriptionPanelSPALoad` | SPA loads; `window.MPrescriptionPanel` defined; `window.MNappiPicker` defined |
| `TestPrescriptionPanelRendering` | Empty state; add-drug appends row; NAPPI picker input visible; `cipro` search shows results; selection populates drug_name |
| `TestCheckPrescriptionSafetyEndpoint` | Returns list; `get_drug_master_by_nappi` returns None for unknown; ciprofloxacin NAPPI CV exists in fixtures |

### Judgment Calls

1. **Drug Master is platform-level, not practice-scoped.** A medicine catalogue has no meaningful
   tenant scoping — any doctor in any practice prescribes from the same SAHPRA-approved list.
   DocPerms (read for Practice Doctor/Admin) replace a PQC.

2. **ATC-class matching via `Patient Allergy.custom_atc_code`** rather than a Link field.
   A free-text ATC code supports manually entered class allergies (e.g. "J01MA" entered by the
   receptionist without needing a Code Value record). A Link would require the Code Value to exist
   first — adding friction without safety benefit.

3. **`before_save` uses `frappe.msgprint` (non-blocking)** — not `frappe.throw`.  SA clinical
   workflows require prescriber override capability for documented clinical reasons.  Hard blocking
   would prevent valid prescribing (e.g. only quinolone that covers Pseudomonas aeruginosa).

4. **Dispensation event stub only (Phase 5)**: `custom_repeats_remaining` field exists but is
   not decremented.  A `before_save` hook on Stock Entry (`custom_practice` + item matching) is
   deferred to Phase 5 closed-loop dispensation.

5. **`Prescription Override Reason` as child table of Patient Encounter** (not standalone).
   Override reasons are encounter-scoped — there is no use case for querying overrides outside
   the context of the encounter they belong to.  Child table keeps the data model simple and
   isolation is guaranteed by the parent encounter's PQC.

### Acceptance Gates

- Python: `bench --site medic-demo-staging.thedaystar.co.za run-tests --app medic_plus --skip-before-tests`
- Playwright: `env/bin/python -m pytest apps/medic_plus/medic_plus/tests/ui/ -v`

Both must pass before merging to `main`.  The bench toolchain was not available in the development
environment used for this commit; staging run is the acceptance gate.

### Out of Scope (Deferred)

- Dispensation event ingestion from pharmacy system (Phase 5 — event hook stub only)
- E-prescribing transmission to pharmacy networks (Phase 5+)
- Formulary check against medical-aid scheme (Phase 5)
- Full production NAPPI catalogue (current 50+1 row seed is synthetic; production import via `bench import-nappi`)
- Full Drug-Drug interaction table population (Healthcare's `Drug Interaction` doctype is checked but the table is empty on the demo site)

---

## 2026-05-02 — Phase 4 (Issue #31): Telemedicine + AI Augmentation

### Scope

Three parallel capabilities shipped as one phase:
1. **Telemedicine** — video consultation rooms (Jitsi Meet / LiveKit Cloud), patient one-time-token join URLs, HPCSA Booklet 10 informed consent, telemedicine tariff mapping.
2. **AI gateway** — Anthropic SDK wrapper with prompt caching, PHI redaction, spend-cap enforcement, and per-practice feature toggles.
3. **Three AI features** — note generation (Whisper → SOAP), differential diagnosis (top-3 ICD-10), and Rx sanity check (third warning row alongside deterministic checks).

Pre-cleared HITL gates: Anthropic spend agreement signed; sub-processor disclosure updated; Patient AI Consent UX reviewed.

### New DocTypes

#### Practice AI Settings
- **Purpose:** Per-practice AI feature toggles and spend cap.
- **Naming:** `autoname: field:practice` — one record per Practice.
- **Key fields:** `ai_enabled` (master switch), `note_gen_enabled`, `ddx_enabled`, `rx_check_enabled`, `default_model` (Sonnet 4.6 / Opus 4.7), `monthly_spend_cap_usd` (0 = no cap), `current_month_spend_usd` (read-only).
- **PQC:** Practice Admin + Practice Doctor see only their own practice's settings. Healthcare Administrator sees all.
- **Auto-disable:** `_check_and_enforce_spend_cap(practice)` sums `AI Inference Log.cost_usd` for the current calendar month via `frappe.db.sql`; if `total ≥ cap > 0`, sets `ai_enabled = 0`.

#### AI Inference Log
- **Purpose:** Append-only audit trail for every AI inference call.
- **Naming:** `AIL-.YYYY.-.#####`
- **Key fields:** `practice`, `encounter`, `practitioner`, `feature` (note_gen/ddx/rx_check), `input_redacted` (PHI stripped), `output`, `model`, `latency_ms`, `cost_usd`, `practitioner_action` (Pending/Accepted/Edited/Discarded).
- **Validation:** `validate()` scans `input_redacted` for 13-digit runs (SA ID pattern) and throws if found — belt-and-suspenders against PHI leakage.
- **PQC:** Practice Admin/Doctor see their practice's logs. Healthcare Administrator sees all.

#### Telemedicine Consent
- **Purpose:** Records patient's informed consent for telemedicine under HPCSA Booklet 10.
- **Naming:** `TC-.YYYY.-.#####`
- **Validity:** 12 months from `consent_date`. `expiry_date` is auto-set in `before_insert`.
- **Consent text:** Full HPCSA Booklet 10 telemedicine policy text stored verbatim on each record so it survives future policy changes.
- **Re-prompt:** `get_tele_consent_status(patient, practice)` returns `"active" | "expired" | "revoked" | "required"`. UI re-prompts on `expired` or `required`.
- **PQC:** Practice staff see their practice's consents; Patient role sees only their own record.

### Custom Fields Added

| DocType | Field | Type | Purpose |
|---------|-------|------|---------|
| Patient | `custom_ai_consent` | Check | Master gate — AI calls blocked if False regardless of practice settings |
| Patient Appointment | `custom_video_section` | Section Break | Groups telemedicine fields |
| Patient Appointment | `custom_consultation_type` | Select (In-Person/Telemedicine/Phone) | Consultation modality |
| Patient Appointment | `custom_video_room_id` | Data (read-only) | Room ID set by `create_room()` |
| Patient Appointment | `custom_video_join_url` | Data (read-only) | Practitioner URL |
| Patient Appointment | `custom_patient_join_url` | Data (read-only) | Patient one-time-token URL |

All fields added to `fixtures/custom_field.json` and `hooks.py` filter list.

### Medic Plus Settings — New Fields

| Field | Purpose |
|-------|---------|
| `anthropic_api_key` | Anthropic SDK auth |
| `openai_api_key` | Whisper transcription |
| `video_provider` | "jitsi" (default) or "livekit" |
| `video_base_url` | Jitsi server or LiveKit base URL |
| `livekit_api_key` / `livekit_api_secret` | LiveKit Cloud auth |

### API Modules

#### `medic_plus.api.ai` — AI Gateway

```python
redact_phi(text, phi_map) → (redacted_text, token_map)
restore_phi(text, token_map) → original_text
call_claude(*, system, user, practice, feature, model, patient_ai_consent) → dict
generate_soap_note(audio_b64, encounter, practice, practitioner, patient_ai_consent, patient_phi) → dict
suggest_ddx(subjective, objective, practice, practitioner, encounter, patient_ai_consent) → dict
rx_sanity_check(medications, allergies, practice, practitioner, encounter, patient_ai_consent) → dict
```

**PHI redaction design:**
- `_PHI_FIELDS`: `patient_name, email, mobile, phone, dob, custom_sa_id_number, address, first_name, last_name, middle_name`
- Each PHI value is hashed via SHA-256 → `[PATIENT_<8-hex>]` token. Deterministic within one call.
- Sub-tokens (first/last name split on whitespace/comma) are also redacted individually.
- Substitution is longest-match-first to prevent partial replacement.
- `restore_phi()` inverts the token map to put values back into AI output before returning to the caller.
- `AI Inference Log.input_redacted` stores the redacted text only — raw PHI never persists.

**Anthropic SDK integration:**
- Lazy client instantiation: `_get_anthropic_client()` is patched in all tests.
- System prompt sent as a list block with `cache_control: {"type": "ephemeral"}` — activates Anthropic prompt caching.
- Default model: `claude-sonnet-4-6`. Opus 4.7 opt-in per practice for DDx.
- Cost tracked: `(input_tokens × input_rate + output_tokens × output_rate) / 1_000_000` USD.

**Enforcement chain (call_claude):**
1. `patient_ai_consent == False` → PermissionError before any API call.
2. `Practice AI Settings.ai_enabled == False` → PermissionError.
3. `Practice AI Settings.<feature>_enabled == False` → PermissionError.
4. Call Anthropic API.
5. `_check_and_enforce_spend_cap(practice)` — auto-disable if over cap.
6. `_log_inference(...)` — append AI Inference Log row.

#### `medic_plus.api.tele` — Telemedicine Room Management

```python
create_room(appointment, practice, patient) → {room_id, practitioner_url, patient_join_url, patient_token}
get_tele_consent_status(patient, practice) → {status, consent?}
record_tele_consent(patient, practice) → {consent, expiry_date}
validate_patient_token(token, room_id) → {valid, appointment?}
```

**Room ID:** `medic-{frappe.generate_hash(appointment, 10).upper()}` — opaque, collision-resistant.

**Patient join URL:** `{site_url}/teleconsult/{room_id}?token={patient_token}&role=patient`
- Token stored in Frappe cache with 2-hour TTL (`tele_patient_token:{token}` → appointment name).
- Token is bound to the appointment's room_id; mismatched claims are rejected.

**Provider selection:** `Medic Plus Settings.video_provider` — "jitsi" (default, room = URL path) or "livekit" (room creation via LiveKit Server SDK).

### Web Page: `/teleconsult/<room_id>`

Authenticated Jinja page. Context resolved in `www/teleconsult/index.py`.

**Practitioner view:**
- Split layout: embedded Jitsi iframe (left) + Encounter Editor side-panel (right).
- Side panel: SOAP textareas (Subjective / Objective / Assessment / Plan).
- "Start Dictation" button: `MediaRecorder` captures 30s of audio → base64 → `generate_soap_note()` → fills SOAP fields. AI Draft badge shown.
- "Sign Encounter" button: saves the encounter.

**Patient view:**
- `?role=patient&token=<token>` — token validated server-side via `validate_patient_token()`.
- Valid: embedded Jitsi iframe (full width).
- Invalid/expired: waiting room spinner + error message.

### Permission Query Conditions (New)

| DocType | Function |
|---------|----------|
| Practice AI Settings | `get_practice_ai_settings_permission_query` |
| AI Inference Log | `get_ai_inference_log_permission_query` |
| Telemedicine Consent | `get_telemedicine_consent_permission_query` |

### Tests

#### Python (`medic_plus/api/test_ai.py`) — 12 test methods across 5 classes

| Class | Behaviours |
|-------|-----------|
| `TestPhiRedactor` | SA ID redacted; patient name + sub-tokens redacted; email/mobile/DOB redacted; tokens deterministic within one call; `restore_phi` round-trips; corpus fuzz (3 patients, 6 PHI fields each — no sub-token ≥4 chars leaks into redacted output) |
| `TestAiGatewayMocked` | `call_claude()` returns text + latency/cost; system prompt carries `cache_control`; blocked when practice AI disabled; blocked when patient consent False |
| `TestMonthlySpendCapAutoDisable` | Under-cap does not disable; over-cap sets `ai_enabled=0`; zero cap never disables |
| `TestNoteGeneration` | SOAP note fills four sections; PHI not present in outbound Claude payload |
| `TestDifferentialDiagnosis` | Returns 3 candidates with icd_code + description |
| `TestRxSanityCheck` | Returns warning text for interaction |

#### Python (`medic_plus/api/test_tele.py`) — 6 test methods across 2 classes

| Class | Behaviours |
|-------|-----------|
| `TestCreateRoom` | Returns room_id + practitioner_url + patient_join_url + patient_token; token appears in patient_join_url |
| `TestTelemedicineConsentCheck` | Active, expired, revoked, required statuses |

#### Playwright (`medic_plus/tests/ui/test_telemedicine_ai.py`) — 9 test methods across 5 classes

| Class | Behaviours |
|-------|-----------|
| `TestPracticeAiSettingsUi` | List reachable; new form shows ai_enabled; spend cap field visible |
| `TestPatientAiConsentUi` | Patient form has custom_ai_consent field |
| `TestPatientAppointmentTeleFields` | Appointment form has consultation_type; options include Telemedicine/Phone |
| `TestTeleconsultPage` | Loads for authenticated admin; unauthenticated redirects to login |
| `TestAiInferenceLogUi` | List reachable; new form shows input_redacted + practitioner_action |
| `TestTelemedicineConsentUi` | List reachable; form has HPCSA acknowledgement; consent API endpoint works |

### Design Decisions

| Decision | Reason |
|----------|--------|
| PHI redaction via deterministic SHA-256 tokens | Idempotent — same input always produces same token; allows `restore_phi()` to swap tokens back into AI output if needed |
| `restore_phi()` available but not used in SOAP output | SOAP note is stored as AI draft for practitioner review; PHI-safe version stored in AI Inference Log; practitioner supplies context via real encounter record |
| Anthropic client instantiated lazily | `_get_anthropic_client()` is patchable before any module-level import; keeps CI clean with no live network |
| `cache_control: ephemeral` on system prompt | Activates Anthropic prompt caching — clinical system prompts repeat across many calls; saves 90%+ of input-token cost on cached portion |
| Monthly cap via `frappe.db.sql` sum | Avoids loading every AI Inference Log doc into memory; single SQL aggregate per call; zero-cap = unconditional skip |
| Patient join URL uses one-time token in Redis cache | Token is bound to appointment → room_id; 2-hour TTL prevents indefinite access; token is never the appointment name (opaque) |
| Jitsi as default provider | Self-hosted option; no SDK dependency; room = URL path; zero provisioning cost for testing |
| LiveKit as opt-in | Requires `livekit` SDK; used when practice needs TURN/STUN or recording |
| AI Inference Log validates SA ID pattern in input_redacted | Belt-and-suspenders: if redactor has a bug, DB-level guard prevents 13-digit run from persisting |
| Telemedicine Consent stores full HPCSA text verbatim | Future policy changes don't retroactively rewrite what was shown to the patient |

### Out of Scope (Deferred)

- Full encounter save/sign workflow from teleconsult side-panel (Phase 4 close)
- Insurance Claim auto-build with telemedicine tariff code 0190V (Phase 4B)
- DDx model override to Opus 4.7 per-practice toggle (field exists; UX deferred)
- Whisper integration with self-hosted server (currently uses OpenAI Whisper endpoint)
- SMS/WhatsApp notification for patient join URL (Africa's Talking — Phase 5)

### Sub-Processor Register

Anthropic added as sub-processor: processes de-identified/tokenized consultation transcriptions for clinical NLP. Raw PHI never leaves the bench — redaction runs server-side before any API call. Updated in Privacy Notice (HITL gate cleared pre-implementation).

---

## 2026-05-02 — Phase 1C (Issue #26): Structured SOAP Encounter + Problem List + Encounter Order

### Scope

Structured clinical documentation layer on top of the existing Frappe Healthcare `Patient Encounter` doctype. Doctors can capture a full SOAP note (Subjective / Objective / Assessment / Plan) with ICD-10-coded assessment, a per-body-system Examination Findings child table, and Encounter Orders (lab / imaging / referral). Submitting an encounter automatically upserts a `Patient Problem List` row for each assessed ICD-10 code, providing a longitudinal active-problem view per patient.

Prerequisites: Phase 1A (SA-PMI Patient Identifiers, issue #24) and Phase 1B (Terminology stack / ICD-10-ZA seed, issue #25) merged into `develop`.

---

### New Doctypes

#### Examination Finding (child table, `istable=1`)

| Field | Type | Notes |
|-------|------|-------|
| `body_system` | Select | General / Cardiovascular / Respiratory / Gastrointestinal / Neurological / Musculoskeletal / Dermatological / ENT / Ophthalmology / Genitourinary / Endocrine / Psychiatric / Other |
| `body_part` | Data (reqd) | Free text e.g. "Chest", "Left knee" |
| `finding` | Small Text (reqd) | Clinical finding text |
| `is_abnormal` | Check | Quick abnormal flag for summary views |

Used as `custom_examination_findings` child table on Patient Encounter.

#### Patient Problem List (standalone, `PPL-.#####`)

One row per (patient, icd10_code) pair — active problem registry for the patient.

| Field | Type | Notes |
|-------|------|-------|
| `patient` | Link → Patient (reqd) | Scoping anchor |
| `custom_practice` | Link → Practice (read_only) | Denormalised from Patient on `before_insert` for fast PQC filter |
| `icd10_code` | Link → Code Value | ICD-10-ZA system |
| `snomed_code` | Link → Code Value | SNOMED-CT-ZA-stub (Phase 5.6 gated) |
| `description` | Data | Human-readable display text auto-filled from Code Value.display |
| `status` | Select | Active / Inactive / Resolved |
| `onset_date` | Date | Populated from encounter_date on first creation |
| `source_encounter` | Link → Patient Encounter | Latest encounter that created/updated this row |
| `severity` | Select | Mild / Moderate / Severe |
| `notes` | Small Text | Free notes |

---

### Custom Fields Added to Patient Encounter (8 new)

| Field | Type | Placement |
|-------|------|-----------|
| `custom_hopi` | Long Text | After `custom_chief_complaint` |
| `custom_subjective` | Long Text | After `custom_hopi` |
| `custom_objective` | Long Text | After `custom_subjective` |
| `custom_assessment_text` | Small Text | After `custom_objective` |
| `custom_assessment_code` | Link → Code Value (ICD-10-ZA filter) | After `custom_assessment_text` |
| `custom_plan` | Long Text | After `custom_assessment_code` |
| `custom_section_examination` | Section Break (collapsible) | After `custom_plan` |
| `custom_examination_findings` | Table → Examination Finding | After `custom_section_examination` |

Existing `custom_chief_complaint` and `custom_encounter_orders` fields from Phase 5.7 are unchanged.

---

### Document Lifecycle — `on_submit` on Patient Encounter

`medic_plus.api.doc_events.on_encounter_submit` fires on Patient Encounter submit and calls two helpers:

1. **`_advance_encounter_orders(doc)`** — promotes any `Draft` Encounter Order rows to `Ordered` status, then calls `doc.db_update()` so child rows persist.

2. **`_upsert_problem_list(doc)`** — reads `custom_assessment_code` (ICD-10-ZA `Code Value` name). If blank, no-op. Otherwise:
   - Looks up `(patient, icd10_code)` in `Patient Problem List`.
   - **Existing row:** `frappe.db.set_value` to set `source_encounter` + `status = Active`.
   - **New row:** `frappe.get_doc(...).insert(ignore_permissions=True)` with `description` pulled from `Code Value.display`, `onset_date` from `encounter_date`, `custom_practice` from encounter (falls back to patient's practice).
   - Idempotent: two submits for the same (patient, ICD-10 code) yield exactly one Problem List row.

---

### Permission Query Condition

`get_patient_problem_list_permission_query(user)` in `api/permissions.py`:

- Platform admin → `""` (unrestricted).
- Patient role → `tabPatient Problem List.patient = <patient_for_user>`.
- Practice staff → `tabPatient Problem List.custom_practice = <practice>` (direct filter on denormalised field; subquery via Patient acts as defence in depth for pre-migration rows if any).
- No Practice Member row → `"1=0"`.

Registered in `hooks.py` under `permission_query_conditions`.

---

### Custom DocPerm (3 new rows)

| DocType | Role | Read | Write | Create | Delete |
|---------|------|------|-------|--------|--------|
| Patient Problem List | Practice Admin | ✓ | ✓ | ✓ | ✓ |
| Patient Problem List | Practice Doctor | ✓ | ✓ | ✓ | — |
| Patient Problem List | Practice Receptionist | ✓ | — | — | — |

---

### Endpoint: `get_encounter_detail(encounter)`

Whitelisted in `medic_plus.api.daystar_health`:

- **Cross-tenant guard:** reads `custom_practice` from the encounter; raises `frappe.PermissionError` if it doesn't match the caller's active Practice.
- **POPIA whitelist:** never emits `custom_sa_id_number` or any non-clinical patient field.
- **Payload shape:**
  ```json
  {
    "encounter": {
      "name", "patient", "encounter_date",
      "chief_complaint", "hopi", "subjective", "objective",
      "assessment_text", "assessment_code", "plan",
      "examination_findings": [ { body_system, body_part, finding, is_abnormal } ],
      "orders": [ { order_type, order_name, status, notes } ]
    },
    "problem_list": [ { name, icd10_code, description, status, onset_date, severity } ]
  }
  ```

---

### SPA: `meridian-new-visit.jsx` (upgraded)

The drawer previously only created a `Patient Appointment`. It now creates a full `Patient Encounter` with four tabbed sections:

| Tab | Content |
|-----|---------|
| **Schedule** | Patient, Practitioner, Date, Time, Appointment Type, Chief Complaint |
| **SOAP Notes** | HOPI, Subjective, Objective, Assessment Text, ICD-10 code picker (debounced 300ms via `search_icd10`), Plan |
| **Examination** | Dynamic row editor: Body System (Select), Body Part, Finding; each row has a remove button. "Add finding" button appends a blank row. |
| **Orders** | Dynamic row editor: Order Type (Lab/Imaging/Referral/Immunisation), Order Name. "Add order" button appends a blank row. |

On submit, the drawer POSTs a `Patient Encounter` document (not `Patient Appointment`) via `frappe.client.insert`. Child rows with blank required fields are filtered before sending. `custom_practice` is stamped server-side by `set_practice_on_insert`.

`data-testid` attributes on all interactive elements (tabs, fields, row editors) for Playwright coverage.

---

### Tests

#### Python (`medic_plus/api/test_soap_encounter.py`) — 10 test methods across 4 classes

| Class | Behaviours |
|-------|-----------|
| `TestSOAPEncounterTracer` | SOAP fields persist on submit; Examination Finding row persists with body_part + finding; Encounter Order row promoted to Ordered; Patient Problem List created with Active status; Practice B PQC blocks encounter read; Practice B PQC blocks Problem List read |
| `TestSOAPPQCShape` | PPL PQC scopes to practice; Admin gets unrestricted; orphan gets 1=0 |
| `TestProblemListUpsert` | Second encounter with same ICD-10 does not duplicate Problem List row |
| `TestEncounterPayloadPOPIA` | `get_encounter_detail` happy path returns correct keys; cross-practice call raises PermissionError |

`IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Healthcare Practitioner"]` guards traversal into ERPNext test modules.

#### Playwright (`medic_plus/tests/ui/test_soap_encounter_ui.py`) — 9 test methods across 2 classes

| Class | Behaviours |
|-------|-----------|
| `TestNewEncounterDrawer` | New-visit button visible; drawer opens; Schedule tab fields render; 4 section tabs visible; SOAP tab text areas render; ICD-10 search shows dropdown; Examination tab add-row works; Orders tab add-row works |
| `TestEncounterDetailEndpoint` | `get_encounter_detail` payload shape; no SA ID leakage; cross-practice returns 403 (urllib second-session pattern) |

---

### Design Decisions

| Decision | Reason |
|----------|--------|
| `custom_practice` denormalised on Patient Problem List | Direct column filter avoids a subquery on every list view. `before_insert` controller populates it from `Patient.custom_practice` at creation time. |
| Upsert keyed on `(patient, icd10_code)` | One active problem per code per patient — avoids proliferating duplicate rows from repeated encounters for the same chronic condition. |
| Encounter Orders promoted from Draft → Ordered on submit | Submit signals clinical intent; "Ordered" means the request has been authorised. Routing to lab providers is deferred (Phase 2). |
| `get_encounter_detail` returns `problem_list` for the whole patient, not just the encounter | SPA renders the full active-problem list alongside any open encounter, so the drawer doesn't require a second API call. |
| SOAP fields as Custom Fields (not new DocType) | Patient Encounter is a Frappe Healthcare core doctype; adding a separate SOAP child would break the standard encounter workflow. Custom Fields on the base encounter keep compatibility with all Healthcare module features (Vital Signs, Drug Prescriptions, etc.). |
| `Examination Finding` as child table, not standalone | Findings are inseparable from the encounter context; standalone creates audit-log overhead with no benefit. |

### Out of Scope (Deferred)

- Allergies-reviewed child table on encounter (Phase 2).
- Medication reconciliation rows (continued / changed / stopped / added) — Phase 2.
- Encounter Order *routing* to lab / imaging providers — Phase 2.
- SNOMED coding of findings (IHTSDO licence gated — Phase 5.6 / #38).
- Antenatal / chronic-disease / well-child encounter templates already exist (Phase 5.7–5.9); SOAP fields are additive and do not conflict.
- Referral letter Composition with FHIR — Phase 3.

---

## 2026-04-30 — Phase 1B (Issue #25): Terminology stack

### Scope

Six FHIR-canonical Code Systems registered with curated seed catalogues, idempotent bench import commands, per-system whitelisted search endpoints, and a generalised SPA picker. Underpins downstream phases (claims, FHIR export, drug-allergy matching).

### Code Systems Registered (fixture)

| System | URI | Seed rows | Notes |
|--------|-----|-----------|-------|
| `ICD-10-ZA` | `http://hl7.org/fhir/sid/icd-10-za` | 34 | SA-canonical diagnosis codes — repointed from old `ICD-10` system in patch `migrate_icd10_to_icd10_za` |
| `NAPPI` | `https://www.nappi.co.za` | 50 | Synthetic SA medicine codes — production replaces via `bench import-nappi` (NAPPI directory licence required) |
| `LOINC` | `http://loinc.org` | 50 | Common SA primary-care lab analytes (CBC, U&E, lipids, HbA1c, HIV viral load, CD4, etc.) |
| `UCUM` | `http://unitsofmeasure.org` | 34 | Common units for FHIR Quantity datatype — vitals, lab results |
| `ATC` | `http://www.whocc.no/atc` | 48 | 14 anatomical groups + 34 curated drug classes — drives Phase 1D drug-allergy class matching |
| `SNOMED-CT-ZA-stub` | `http://snomed.info/sct/za` | 5 | Placeholder only — full catalogue gated on IHTSDO Affiliate licence (Phase 5.6 / #38) |

### Bench Commands (`medic_plus/commands/__init__.py`)

Six thin click wrappers over `medic_plus.api.terminology_import.import_<system>(csv_path)`:

```
bench --site SITE import-icd10  path/to/codes.csv
bench --site SITE import-nappi  path/to/codes.csv
bench --site SITE import-loinc  path/to/codes.csv
bench --site SITE import-ucum   path/to/codes.csv
bench --site SITE import-atc    path/to/codes.csv
bench --site SITE import-snomed path/to/codes.csv
```

CSV format: `code,display` header + N rows. Missing/blank `code` rows are skipped.

### Importer (`medic_plus/api/terminology_import.py`)

Single private `_import_csv(system, uri, csv_path)` helper handles all six systems. Idempotent: row name follows Code Value's controller autoname (`{code}-{system}`), so re-running an unchanged CSV is a no-op; a CSV with a new `display` for an existing code updates in place.

### Whitelisted Search Endpoints (`medic_plus/api/daystar_health.py`)

| Endpoint | System scoped to |
|----------|-----------------|
| `search_icd10` | ICD-10-ZA (was ICD-10 — Phase 1B repoint) |
| `search_nappi` | NAPPI |
| `search_loinc` | LOINC |
| `search_ucum` | UCUM |
| `search_atc` | ATC |
| `search_snomed` | SNOMED-CT-ZA-stub |

All share `_search_code_values(system, query, limit)` private helper. Return shape: `[{ name, code, display }]`. Query matches case-insensitively on code-prefix OR display-substring. Limit clamped to [1, 100], default 25.

### SPA: Generalised picker

`meridian-code-picker.jsx` exports `MCodePicker` (generic, takes `endpoint` + `placeholder` + `emptyText` + `testid`) plus `MNappiPicker` and `MLoincPicker` thin wrappers. The existing `MIcd10Picker` is rewritten as a thin wrapper over `MCodePicker` so call-sites in `meridian-patient.jsx` (Conditions tab) keep working unchanged.

### Migration

`migrate_icd10_to_icd10_za` (post_model_sync): `UPDATE tabCode Value SET code_system='ICD-10-ZA' WHERE code_system='ICD-10'`. Idempotent; re-running on a migrated DB is a no-op.

Patch `add_custom_practice_indexes` was tightened with a `_column_exists` guard so child tables (Patient Identifier, etc.) that inherit scoping from their parent don't trip the blind ALTER TABLE.

### Tests (8 IntegrationTestCase, all green)

| Class | Behaviour |
|-------|-----------|
| `TestIcd10ImportTracer` | First import creates 50 rows; reimport idempotent (created=0, updated=50); changed display refreshes in place |
| `TestMultiSystemImporters` | NAPPI importer end-to-end; cross-system disambiguation (same literal code in two systems → two distinct rows) |
| `TestPerSystemSearchEndpoints` | `search_nappi` returns only NAPPI rows; `search_loinc` only LOINC; `search_icd10` regression — now returns only ICD-10-ZA |

### Out of Scope (Deferred)

- Full SNOMED CT-ZA catalogue import (gated on IHTSDO Affiliate licence — Phase 5.6 / #38)
- Production NAPPI catalogue (current 50-row seed is synthetic — replace via licence-bound bench import)
- Full ICD-10-ZA Master Industry Tariff catalogue (current 34-row seed is the SA-relevant subset for Phase 1; full ~25k-row import via `bench import-icd10` in Phase 4 billing)
- LOINC ZA-specific extensions (NHLS local codes)
- Picker UX integration into Phase 1D prescriptions (NAPPI) / Phase 2 lab orders (LOINC) — this slice ships the components, not the call-sites

---

## 2026-04-30 — Phase 1A (Issue #24): SA-PMI Patient Identity

### Scope

Multi-identifier patient registration with SA ID checksum validation, POPIA consent gate, fuzzy duplicate detection, and SPA registration form upgrade. Implements the SA Patient Master Index (SA-PMI) identity layer on top of the existing Frappe Healthcare Patient doctype.

### DocType Created

#### Patient Identifier (child table of Patient)
- **Purpose:** Stores one or more identity documents per patient. Exactly one row may carry `is_primary = 1`.
- **Fields:** `id_type` (Select: SAID / Passport / Refugee / Asylum / BirthCert / NHID / Other), `id_value` (Data, reqd), `is_primary` (Check), `country` (Link → Country, optional), `expiry_date` (Date, optional).
- **Naming:** `istable=1` — child records use Frappe's implicit numeric `idx`.
- **File:** `medic_plus/medic_plus/doctype/patient_identifier/`

### Custom Fields Added to Patient (Fixtures)

| Field | Type | Purpose |
|-------|------|---------|
| `custom_identifiers` | Table → Patient Identifier | Child table of identifier rows |
| `custom_popia_consent_special` | Check | POPIA Section 27 consent for SA ID / race / language collection |
| `custom_nhid` | Data (indexed) | NHID slot — HPRS integration deferred to a later phase |
| `custom_race` | Select | African / Coloured / Indian or Asian / White / Other / Prefer not to say |
| `custom_home_language` | Select | SA 11 official languages + Other |
| `custom_preferred_language` | Select | SA 11 official languages + Other |

All exported via `fixtures/custom_field.json`; field names in the `hooks.py` filter list.

### New Python Modules

#### `medic_plus/api/sa_id.py`
- `validate_said(id_number)` — raises `frappe.ValidationError` if the 13-digit SA ID fails the SA Dept of Home Affairs checksum:
  1. Sum digits at 0-indexed positions 0, 2, 4, 6, 8, 10 → A
  2. Concatenate digits at positions 1, 3, 5, 7, 9, 11 → N; compute N × 2; sum individual digits → B
  3. `check_digit = (10 − (A + B) % 10) % 10` must equal `id_number[12]`
- `parse_said(id_number)` — returns `{dob: "YYYY-MM-DD", sex: "Male"|"Female"}`. Year century: YY ≤ current two-digit year → 2000+YY, else 1900+YY. Sex: sequence digits 6–9 ≥ 5000 → Male.

**Note:** The issue specification cites `8501015009087` as checksum-valid. The standard algorithm yields check digit 6 for that DOB/sequence combination; `8501015009086` is the canonical test ID used in the test suite. The discrepancy is documented in `test_patient_pmi.py`.

#### `medic_plus/api/patient_identity.py`
- `find_duplicate_patients(patient_name, practice, dob=None, id_value=None)` — `@frappe.whitelist()`. Returns a list of potential duplicate patient dicts. Non-blocking (never raises). Scoring:
  - Exact `id_value` match (any id_type) → always returned.
  - Soundex match on first token of `patient_name` + DOB within ± 1 day → candidate.
  - Levenshtein distance ≤ 2 on lower-cased `patient_name` + DOB within ± 1 day → candidate.
- Soundex and Levenshtein are vendored (pure Python, no external deps).

### Document Lifecycle Hooks

`Patient.validate` → `medic_plus.api.doc_events.validate_patient_identifiers`:
1. **POPIA gate:** if any row has `id_type = "SAID"` and `custom_popia_consent_special = 0` → `ValidationError`.
2. **SA ID checksum:** for each SAID row, calls `validate_said()`.
3. **DOB/sex derivation:** after validation, `parse_said()` populates `doc.dob` and `doc.sex` if not already set.
4. **Primary constraint:** `sum(is_primary for row in identifiers) > 1` → `ValidationError`.

### Permission Query Condition

`Patient Identifier` PQC (`get_patient_identifier_permission_query`):
- Platform admin → unrestricted (`""`).
- Patient role → `parent = <patient_name_for_user>`.
- Practice staff → `parent IN (SELECT name FROM tabPatient WHERE custom_practice = <practice>)`.

Registered in `hooks.py`; CustomDocPerm rows for Practice Admin (read/write/create/delete), Doctor (read/write/create), Receptionist (read/write/create) exported in `fixtures/custom_docperm.json`.

### Endpoints

| Method | Auth | Purpose |
|--------|------|---------|
| `medic_plus.api.patient_identity.find_duplicate_patients` | authenticated | Fuzzy-match candidates, non-blocking |
| `medic_plus.api.practice_resolver.get_active_practice` | authenticated | Returns the session user's practice (now `@frappe.whitelist()`) |

### SPA: meridian-patients.jsx

Added **Register Patient** side-drawer to the Patients list screen:
- "Register Patient" button (top-right of patients page header); disabled until practice resolves.
- Drawer sections: Demographics (first/last name, sex, DOB, email, mobile), Identifier (id_type picker + id_value input), POPIA consent checkbox (shown only when `id_type = "SAID"`), Language & Background (race, home_language, preferred_language — optional).
- Non-blocking duplicate warning banner shown on name/DOB/ID blur.
- Client-side POPIA gate: blocks submission with an inline error if consent is missing for SAID.
- On success: closes drawer and navigates to the new patient's detail screen.

### Tests

#### Python (`medic_plus/api/test_patient_pmi.py`) — 12 test methods across 5 classes

| Class | Behaviors |
|-------|-----------|
| `TestSAIDTracerBullet` | Identifier row persists; DOB/sex derived from SA ID; PQC denies cross-practice receptionist |
| `TestSAIDChecksumValidation` | Bad check digit rejected; 12-digit ID rejected; valid ID accepted |
| `TestPOPIAConsentGate` | SAID without consent raises; Passport without consent allowed |
| `TestPrimaryIdentifierConstraint` | Two primaries raises; multiple identifiers one-primary accepted |
| `TestFuzzyDuplicateDetection` | Exact identifier match returned; Soundex + DOB proximity returned |

#### Playwright (`medic_plus/tests/ui/test_patient_pmi_ui.py`) — 6 test methods

Register Patient button visible; drawer opens; SAID shows POPIA checkbox; Passport hides it; race/language fields rendered; SAID-without-consent shows inline error.

### Design Decisions

| Decision | Reason |
|----------|--------|
| Soundex + Levenshtein vendored (pure Python) | No external packages; Frappe bench envs do not guarantee `jellyfish` or `python-Levenshtein` |
| POPIA consent gated at validate(), not before_insert() | `validate` fires before Frappe's `_validate()` mandatory check, so `doc.dob`/`doc.sex` set here persist |
| Child table PQC uses parent-subquery (not denormalized `custom_practice`) | Patient Identifier is always accessed through the parent Patient; subquery is a one-hop join the DB can optimise |
| `custom_nhid` is a slot only | HPRS national lookup integration is explicitly out-of-scope; the field reserves the column for the future phase |
| SAID check digit 7 vs 6 discrepancy | Issue #24 cites `8501015009087` as checksum-valid; the algorithm (odd-sum + doubled-even-concat) yields 6, not 7. Test suite uses `8501015009086`. |

### Out of Scope (Deferred)

- Biometric capture (Phase 5+)
- HPRS national patient lookup via NHID (field is a slot only)
- Patient demographic change request workflow (Phase 3 with patient portal)
- Telemedicine consent capture (Phase 4)

---

## 2026-04-29 — Phase 1J (Issue #8): Daystar Health profile — wired + password change

### Scope
Slice 5 of 5 (final) wiring `/daystar-health`. Replaces the hardcoded provider profile with the logged-in user's real data, and wires the password-change form to Frappe's standard endpoint. Notifications tab is removed from the SPA's profile sidebar — no schema backing.

### Endpoint: `daystar_health.get_my_practitioner_profile()`
Joins User core (name, email, phone, user_image) with the Healthcare Practitioner linked via the user's Practice Member row (department, HPCSA number, practice number). Adds a top-level `two_factor_authentication` boolean derived from `frappe.utils.user.user_has_2fa` since User has no direct 2FA field.

Same `frappe.PermissionError` no-practice gate as every other Daystar Health endpoint.

### Frontend rewire (`meridian-profile.jsx`)
- Three render states: skeleton, error card, ready (two tabs only — Account, Security).
- **Profile tab**: read-only fields rendered as styled disabled boxes (`<ReadOnlyField>` helper). No "Save changes" button anywhere on the tab. Footer note tells the user to contact their practice administrator for changes.
- **Security tab**: password-change form (current / new / confirm) posts to `frappe.core.doctype.user.user.update_password`. Success/error feedback inline. 2FA shown read-only with status badge ("Enabled" / "Not configured") and a pointer to the Frappe Desk for setup.
- **Notifications tab removed** — no `User Notification Preference` doctype, so any UI we'd ship would be misleading.

### Sidebar fix
The bottom-of-sidebar "Sign out" button was wired to `go('login')` — that just changed the SPA route; the Frappe session was untouched. Fixed to call `window.meridianApi.logout()` so it actually ends the session. Also added `data-testid="nav-profile"` and `data-testid="nav-signout"` on those buttons.

### Tests
- Python: 2 new — endpoint rejects no-practice user (tracer); endpoint returns the documented payload (User + Practitioner blocks + 2FA boolean).
- Playwright: 2 new — profile renders read-only with no Save button + Notifications tab absent; password change round-trip (uses a throwaway Practice user fixture, changes the password through the SPA, then signs in with the new password to prove end-to-end).

### Slice 5 wraps Phase 1 of the SPA wiring (#4 → #5 → #6 → #7 → #8)
The five issues delivered:
- #4 — auth flow + foundation (`practice_resolver`, page bootstrap, `meridian-api.js`)
- #5 — dashboard composite + frontend
- #6 — patients list (REST resource API + server-side search/pagination)
- #7 — patient detail composite (POPIA-filtered, per-tab capped)
- #8 — profile read-only + password change

Outstanding follow-up: **Issue #12** (Custom DocPerm fixtures for Practice roles) — currently unblocked on staging via a Physician role on the test user, but needs to land before the SPA can serve real Practice users without that workaround.

---

## 2026-04-29 — Phase 1I (Issue #7): Daystar Health patient detail — wired to composite endpoint

### Scope
Slice 4 of 5 wiring `/daystar-health`. Replaces the static `MH_DATA` lookups on the patient detail screen with a single composite endpoint that returns all six tabs in one round trip.

### Deep module: `patient_summary`
- `build_patient_summary(patient_name, practice)` — orchestrator. Fetches Patient + Patient Encounters (last 20) + Vital Signs (last 12) + active medications de-duped across encounters + Lab Tests (last 20) + Frappe Comments on the Patient (last 20). Hands them to the format helper.
- `_format_patient_summary(...)` — pure transformation. Caps each tab and applies the **POPIA whitelist**: only the fields in `_PATIENT_PUBLIC_FIELDS` (`name / patient_name / dob / sex / mobile / email / status`) survive into the patient block. `custom_sa_id_number` is impossible to leak — it never appears in the response, even if the caller hands the helper a row containing it.

### Endpoint: `daystar_health.get_patient_detail(patient)`
- Cross-tenant guard: looks up the patient's `custom_practice` and refuses with `frappe.PermissionError` if it doesn't match the caller's active Practice. Same error class as no-practice, so an attacker can't probe Practice membership of arbitrary IDs by looking at the response code.
- Returns the composite payload from `build_patient_summary`.
- "See full record" links per tab go to the Frappe Desk filtered list — built into the payload as `full_record_links`.

### Frontend rewire (`meridian-patient.jsx`)
- Three render states: skeleton, error (with "Back to patients" CTA), ready.
- Ready state has six tabs: Overview / Visits / Vitals / Medications / Labs / Notes — all hydrated from the same fetch, no waterfall on tab switch.
- Notes tab renders Comment HTML via `dangerouslySetInnerHTML` (Frappe's HTML Editor field — same trust boundary as the Frappe Desk activity feed).

### Tests
- Python: 4 new unit tests — POPIA exclusion (the tracer), per-tab caps (visits/labs/meds/notes capped at 20, vitals at 12), endpoint rejects no-practice, endpoint rejects cross-tenant patient request.
- Playwright: 2 new tests — detail screen renders all 6 tab containers (with search filter to ensure we click a row in our own Practice when admin's view bypasses Patient PQC); response body of the composite call asserted to never contain `custom_sa_id_number`.

### Out of scope (later slices)
- Profile + password change (#8) — last slice.

### Surfaced gap (Issue #12)
While testing as a real Practice user (selfserve.test), discovered that medic_plus ships no Custom DocPerm fixtures granting Practice Admin / Practice Doctor / Practice Receptionist roles read access on Patient and related Healthcare doctypes. Practice users get 403 from `/api/resource/Patient` *before* the PQC runs because the role-permission gate isn't open. Tracked in #12 with a workaround (Physician role added to test user).

---

## 2026-04-29 — Phase 1H (Issue #6): Daystar Health patients list — wired to REST resource API

### Scope
Slice 3 of 5 wiring `/daystar-health`. Replaces the static `MH_DATA.PATIENTS` array on the patients screen with a real, server-side paginated/searchable/sortable list backed by Frappe's REST `Patient` resource.

### No new backend module
Per Q11, the patients list is a direct REST consumer — `meridianApi.resource("Patient", {fields, or_filters, order_by, limit_start, limit_page_length})`. PQC (`get_patient_permission_query` in `api/permissions.py`) handles tenant scoping for free, so we get cross-tenant safety without writing any new endpoint.

### Frontend rewire (`meridian-patients.jsx`)
- Three render states: skeleton (during load), error (toast + inline card), ready (table or empty-state card).
- **Search**: 300ms-debounced input, refetches via `or_filters` across `patient_name`, `mobile`, `email`. Clearing the input restores the unfiltered list.
- **Pagination**: real `limit_start / limit_page_length / total` with prev/next. Pagination footer shows `start – end of total`. The total comes from a parallel `frappe.client.get_count` (or a wider `or_filters`-based query when searching).
- **Page-size selector**: 25 / 50 / 100. Persists for the session in `sessionStorage` under `daystar.patients.pageSize`.
- **Sort**: server-side `order_by` on `patient_name` (Name) and `dob` (Age — `dob desc` = oldest first). Click header to toggle direction; resets page to 0.
- **Sidebar nav** now exposes `data-testid={`nav-${key}`}` on every nav button so Playwright tests can navigate between screens deterministically.

### Per the design decisions in the issue
Removed: risk / status / provider filter chips (no Frappe backing), MRN column (no field), risk badge, status pill (Stable/Watch/Urgent — those values don't exist), conditions and allergies columns, "Last seen" column (would require joining Patient Encounter — surfaces in slice 4 via the patient detail screen instead), checkboxes / bulk actions, Export and Register buttons.

### Tests
- Python (`api/test_daystar_health.py`): 2 PQC contract tests — Doctor user is restricted to their own Practice; orphan (no Practice Member) gets `1=0`. Mocks at the `_is_platform_admin` / `_get_user_practice` boundary so the test stays a behavior-of-PQC test, not a doctype-fixture test.
- Playwright (`tests/ui/test_daystar_health.py`): 5 tests — list loads with skeleton then renders rows; search filters list and clearing restores; next-then-prev shows different pages then restores; page-size persists in `sessionStorage`; empty state renders for no-match search.

### Out of scope (later slices)
- Patient detail composite (#7) — clicking a row already navigates to `route='patient'`, but that screen still consumes `MH_DATA`.
- Profile + password change (#8).

---

## 2026-04-29 — Phase 1G (Issue #5): Daystar Health dashboard — wired to live Practice data

### Scope
Slice 2 of 5 wiring `/daystar-health`. Replaces the static `MH_DATA` constants on the dashboard screen with a real composite endpoint scoped to the user's active Practice.

### Deep module: `dashboard_aggregator`
- `build_dashboard(*, practice, user)` — orchestrator. Resolves the user's first name, runs Practice-scoped queries against Patient Appointment / Patient / Lab Test / Patient Encounter, then delegates to the format helper.
- `_format_dashboard(...)` — pure transformation. Takes already-fetched values and returns the payload dict. Tested in isolation without a DB so the interesting rules (greeting personalisation, week-volume always 7 days, recent-patients cap at 6, status breakdown of today's appointments) have fast unit coverage.

### Endpoint: `daystar_health.get_dashboard()`
- Thin orchestrator: `practice_resolver.get_active_practice` → `build_dashboard` → return. Surfaces `frappe.PermissionError` unchanged so the SPA can render the no-practice card.

### Frontend rewire (`meridian-dashboard.jsx`)
- On mount, `meridianApi.call('medic_plus.api.daystar_health.get_dashboard')`. Skeleton placeholder during load; toast + inline error card on failure.
- KPI tiles: today's appointments (with status-breakdown subtitle using *real* statuses — Confirmed / Open / Scheduled — not the mock's "checked-in / in-room"), active patients, outstanding labs.
- Today's schedule, week-volume bar chart, recent-patients table all hydrate from the payload.
- Per Q9 design decision: dropped the "Pending refills" KPI tile (no Frappe backing), the "Needs attention" alerts panel (no backing), the MRN/Risk/Status columns on recent patients, the Day/Week/Month toggle, and the "New appointment" button.
- "View full schedule" button links to the Frappe Desk Patient Appointment list filtered by `custom_practice` and today's `appointment_date`.

### Schema realities handled
- `Lab Test` has no `custom_practice` field. The outstanding-labs KPI uses a JOIN through `Patient.custom_practice` rather than schema migration.
- The `checked_in / in_room` statuses in the mock don't exist in `Patient Appointment`. The real statuses (`Confirmed / No Show / Open / Scheduled`) are surfaced verbatim.

### Tests
- Python (`api/test_daystar_health.py`): 4 format-helper unit tests + 2 endpoint contract tests (no-Practice rejection, payload shape on success). Mocks at the boundary so the helper is testable without DB or session.
- Playwright (`tests/ui/test_daystar_health.py`): one test that creates a temporary `Practice Member` row for Administrator (role=Admin to bypass the Doctor → Healthcare Practitioner validation), logs in, asserts the dashboard renders all three KPI tiles, the week-volume chart, today-schedule and recent-patients sections, the greeting block, and the "View full schedule" link with the right `custom_practice` query string. Tears the Practice Member row down on teardown so the slice 1 no-practice tests still pass for Administrator.

### Out of scope (later slices)
- Patients list (#6), patient detail composite (#7), profile + password change (#8).

---

## 2026-04-29 — Phase 1F (Issue #4): Daystar Health SPA — auth flow wired to Frappe

### Scope
Slice 1 of 5 for the `/daystar-health` Single-Page Application: replace the mock authentication with real Frappe auth, and lay the foundation that subsequent screens (dashboard, patients list, patient detail, profile) reuse.

### Deep module: `practice_resolver`
- `get_active_practice(user) -> str` resolves the user's active Practice via `Practice Member`, the single source of truth for "which Practice does this user belong to" across all Daystar Health endpoints.
- Raises `frappe.PermissionError` for Guest and for any user without a Practice Member row. `Healthcare Administrator` role is *not* specially privileged here — admins still need a Practice Member to use this UI (they retain Frappe Desk access for admin work).

### SPA bootstrap
- `www/daystar_health.py` exposes `csrf_token`, `session_user`, and `has_practice` to the template via `get_context()`. Resolving `has_practice` server-side eliminates a first-render round trip and lets the SPA choose its initial route synchronously.
- `meridian-api.js` is the new centralised SPA API client — wraps `fetch` with CSRF + JSON conventions, surfaces `call`, `resource`, `login`, `recoverPassword`, `logout`, `showError`. Every later slice consumes this helper rather than rolling its own.

### Auth screens (`meridian-auth.jsx`)
- `MLoginScreen` posts to `/api/method/login` with username/email + password. In-page error banner on bad credentials. Username (e.g. `Administrator`) and email both accepted (`type="text"` rather than `type="email"`).
- `MRecoverScreen` posts to `frappe.core.doctype.user.user.reset_password`.
- New `MNoPracticeScreen` renders for authenticated users without a Practice Member row. Sign-out posts to `/api/method/logout` with the CSRF token.

### First-render routing
The SPA's `initialRoute()` reads the bootstrap and chooses `login` / `no-practice` / `dashboard` at mount time. Already-authenticated users no longer see the login screen flicker.

### Tests
- Python: 3 unit tests for `practice_resolver` (member returns Practice, no-membership raises, Guest raises). Mocks `frappe.db` to keep tests pure; LocalProxy bound in `setUpModule` to avoid Python 3.14 + ContextVar issues.
- Playwright: 5 tests covering anonymous → login screen, invalid credentials surface in-page error, admin login lands on no-practice card, already-logged-in admin skips login, sign-out returns to login.

### Bug surfaced
Frappe's website page renderer (`template_page.set_pymodule`) maps hyphenated `.html` templates to underscored `.py` companion modules. The pre-existing `daystar-health.py` was therefore dead code — Frappe was looking for `daystar_health.py`. Renamed to fix the bootstrap injection.

### Out of scope (later slices)
- Dashboard, patients list, patient detail, profile — all still consume static `MH_DATA` mocks. Issues #5, #6, #7, #8.

---

## 2026-04-08 — Phase 3: Platform Owner Workspace

### Requirement
Administrator/Healthcare Administrator needs a single workspace to monitor all practices — metrics, charts, quick links, recent activity.

### Workspace: "Medic Plus Platform"
- **Module:** Medic Plus
- **Role restriction:** Administrator + Healthcare Administrator only
- **Sections:** Key Metrics → Analytics → Quick Access → Recent Activity

### Number Cards (6)
| Card | DocType | Filter |
|------|---------|--------|
| Total Practices | Practice | none |
| Active Practices | Practice | is_active=1 |
| Total Patients | Patient | none |
| Today's Appointments | Patient Appointment | appointment_date=Today |
| This Month's Appointments | Patient Appointment | appointment_date this month |
| Sick Notes Issued | Sick Note | docstatus=1 |

### Dashboard Charts (3)
| Chart | Type | DocType | Grouped by |
|-------|------|---------|------------|
| Appointments Over Time | Line | Patient Appointment | appointment_date (daily, last month) |
| Practices by Subscription Plan | Donut | Practice | subscription_plan |
| Patients per Practice | Bar | Patient | custom_practice |

### Shortcuts (6)
New Practice, Practice Members, All Patients, All Appointments, All Sick Notes, Email Account

### Quick Lists (3)
Recent Practices, Recent Appointments, Recent Sick Notes

### Fixtures
Number Card, Dashboard Chart, and Workspace all exported to `fixtures/` and wired into `hooks.py`.

---

## 2026-04-08 — Phase 1: Multi-Tenant Core + Booking Portal

### Requirement
Build a multi-tenant healthcare platform on top of Frappe Healthcare v16. Doctors register a **Practice**, operate independently on a single bench site, and patients can self-book appointments via a public portal.

### Architecture Decision: Practice-as-Tenant
Each **Practice** is the tenant boundary. All Healthcare DocTypes carry a `custom_practice` Link field. Eight Permission Query Conditions enforce data isolation at the database layer — users only query records belonging to their own practice. Platform admins (`Healthcare Administrator` role) see all.

### DocTypes Created

#### Practice
- **Purpose:** Tenant entity. One per doctor/clinic.
- **Naming:** UUID (v16 feature — no guessable sequential IDs)
- **Key fields:** `practice_name`, `slug` (unique, URL-safe, auto-generated), `is_active`, `subscription_plan`, `owner_practitioner`, `logo`, `color`
- **Slug:** Auto-generated from practice name on insert if empty. Validated to be lowercase alphanumeric + hyphens. Uniqueness enforced in controller.
- **File:** `medic_plus/medic_plus/doctype/practice/`

#### Practice Member
- **Purpose:** Links Frappe Users to a Practice with a role (Admin / Doctor / Receptionist).
- **Naming:** UUID
- **Key fields:** `practice`, `user`, `role`, `practitioner`
- **Side effects on save:** Auto-assigns corresponding Frappe role (`Practice Admin` / `Practice Doctor` / `Practice Receptionist`) to the User. Removes role on trash if no other membership exists.
- **Validation:** Prevents duplicate user+practice membership. Doctor role requires `practitioner` field.
- **File:** `medic_plus/medic_plus/doctype/practice_member/`

#### Sick Note
- **Purpose:** Submittable document issued by a doctor. Creates a Patient Medical Record on submit.
- **Naming:** `SN-.YYYY.-.#####`
- **Key fields:** `patient`, `practice`, `practitioner`, `encounter` (optional), `date_issued`, `fit_for_work_date`, `days_off` (auto-calculated), `diagnosis`, `notes`
- **Workflow:** Draft → Submit → Cancel/Amend
- **Side effects:** `before_insert` auto-sets `practice` from session user's Practice Member. `on_submit` creates a Patient Medical Record.
- **File:** `medic_plus/medic_plus/doctype/sick_note/`

### Custom Fields (Fixtures)
Added `custom_practice` (Link → Practice, search_index=1) to:
- `Patient`
- `Patient Appointment`
- `Patient Encounter`
- `Inpatient Record`

### Roles (Fixtures)
- `Practice Admin` — full access within practice
- `Practice Doctor` — create/submit encounters, prescriptions, sick notes
- `Practice Receptionist` — appointments + patients, read-only sick notes

### Permission Query Conditions
Eight conditions in `medic_plus/api/permissions.py`, wired via `hooks.py`:
- `Practice`, `Practice Member` — scoped to user's own practice
- `Patient`, `Patient Appointment`, `Patient Encounter`, `Inpatient Record` — scoped by `custom_practice`
- `Sick Note` — scoped by `practice`
- `Healthcare Practitioner` — visible only if member of same practice

Platform admins (`Healthcare Administrator`) bypass all conditions.

### hooks.py — doc_events
`before_insert` on Patient, Patient Appointment, Patient Encounter, Inpatient Record → `set_practice_on_insert` — auto-stamps `custom_practice` from the session user's Practice Member record.

### v16 Mixin (extend_doctype_class)
`PracticeAwareMixin` extends `Patient Appointment` — validates that the selected practitioner belongs to the appointment's practice.

---

## 2026-04-08 — Phase 2: Public Booking Portal with Email OTP

### Requirement
Patients book appointments via `/book?practice=<slug>` without a Frappe account. Identity verified via email OTP.

### Security Design
Marley Frontend's existing OTP pattern generates the code client-side and stores it in `localStorage` — trivially bypassed via DevTools. We do not replicate this.

**Our pattern:**
- OTP generated server-side (`random.randint(100000, 999999)`)
- Stored in Redis via `frappe.cache.set_value(key, otp, expires_in_sec=600)`
- Never sent to or stored in the browser
- Single-use: deleted from cache immediately on successful verification
- Rate limited: max 3 requests per 10 minutes per email+practice (tracked in Redis)

### API Endpoints (`medic_plus/api/booking.py`)

| Method | Auth | Purpose |
|--------|------|---------|
| `request_booking_otp(practice_slug, email)` | guest | Generate + email OTP, rate-limited |
| `verify_and_book(practice_slug, otp, ...booking_data)` | guest | Verify OTP then atomically create appointment |
| `get_practice_info(practice_slug)` | guest | Public practice details |
| `get_practice_practitioners(practice_slug)` | guest | Active doctors |
| `get_availability(practice_slug, practitioner, date)` | guest | Open time slots |

### Booking Flow
1. Patient fills form (name, email, phone, doctor, date, time slot)
2. Clicks "Send Verification Code" → `request_booking_otp` → branded OTP email sent
3. Enters 6-digit code → `verify_and_book` → OTP verified, appointment created, confirmation email sent
4. Success screen with appointment reference

### Email
- Outbound: `liz@thedaystar.co.za` via `mail.thedaystar.co.za:587` (TLS)
- Configured via Frappe Email Account DocType
- `mute_emails` disabled in site_config

### Portal Page
- URL: `/book?practice=<slug>`
- Jinja template: `medic_plus/www/book/index.html`
- Context: `medic_plus/www/book/index.py`
- Three-step UI: Details → OTP → Success
- Brand colour applied via CSS variable from Practice's `color` field

### Patient Creation
- New patients auto-created on first booking (matched by email on subsequent bookings)
- `custom_practice` stamped on new Patient records

---

## Design Decisions Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-04-08 | Practice uses UUID naming | No guessable IDs for tenant records |
| 2026-04-08 | OTP server-side in Redis, not localStorage | Security — client-side OTP trivially bypassed |
| 2026-04-08 | Permission Query Conditions over row-level security | Native Frappe pattern, applies at ORM layer |
| 2026-04-08 | Single `custom_practice` field on Healthcare DocTypes | Minimal DB footprint, compatible with base Healthcare app |
| 2026-04-08 | verify_and_book is atomic | Prevents partial state: OTP consumed only if appointment succeeds |
| 2026-04-08 | Jinja booking portal (not Vue SPA) | Simpler — no build step, no dependency on marley_frontend |
| 2026-04-13 | Practice naming changed from UUID → PRAC-.##### | UUID names are opaque, break list views, and make debugging harder |
| 2026-04-13 | Two-sided OTP (clinician + patient) for data unmask | POPIA requires affirmative patient consent — one-sided OTP was insufficient |
| 2026-04-13 | Store OTP hashes (SHA-256), never plaintext | Defence-in-depth: even if DB is compromised, OTPs cannot be retrieved |
| 2026-04-13 | urllib + CookieJar for Playwright second-session tests | Frappe's 403 redirect handler destroys page.evaluate context in browser |
| 2026-04-14 | Playwright UI tests mandatory for all features | Regression safety net without needing a staging reset for each PR |

---

## 2026-04-13 — Phase 3B: Subscription Billing + Feature Gates

### Requirement
Practices must be locked to a tier (Free / Basic / Pro). Certain features (inpatient module, SMS reminders, advanced reports) must be unavailable until upgraded. Paystack processes recurring payments.

### Plan catalogue (in-code, `billing.py`)
Plans are defined in `MEDIC_PLANS` dict — no DocType. `Practice.subscription_plan` stores the current key. Avoids schema migration when plan pricing changes.

### `require_feature` decorator
Applied to any endpoint that should be plan-gated:
```python
@frappe.whitelist()
@require_feature("inpatient_module")
def get_inpatient_summary(): ...
```
Raises `frappe.PermissionError` (HTTP 403) if the feature is `False` for the practice's plan. Platform admins bypass unconditionally.

### `/billing` web page
Authenticated Jinja page. Calls `get_billing_summary()` on load. Shows plan, status badge, usage bars, feature chips, and upgrade cards with Paystack checkout buttons.

### Paystack webhook
`paystack_webhook()` validates HMAC-SHA512 signature against `Medic Plus Settings.paystack_secret_key`. On `charge.success`, updates `Practice.subscription_plan` and `subscription_status`.

---

## 2026-04-13 — Phase 3C: Practice Setup Checklist + Patient Portal + Patient PQC

### Practice Setup Checklist
Six-step onboarding tracker. Steps 1-4 are set by the doctor via the UI. Steps 5-6 are auto-completed by `doc_events.py`:
- Step 5: fires on `Practitioner Schedule.after_save`
- Step 6: fires on `Sales Invoice.on_submit` when the company matches the practice's company

### Patient role PQC isolation
Patients get a Frappe User with role `Patient`. Their PQC branches to scope by `User.email == Patient.email` rather than by practice membership. Without this, any patient with a login could see all patients in their practice.

### Patient portal (`/portal`)
Authenticated Jinja page. Shows the logged-in patient's appointments, sick notes, and pending data unmask requests (with a "Deny" button).

---

## 2026-04-13 — Phase 3D: Patient Data Masking (POPIA Hardening)

See Section 7 of TRAINING_MANUAL.md for the full flow.

**New doctypes:** `Data Unmask Request`, `Clinical Access Log`
**New fixtures:** Client Script on Patient form (masking + "View" button)
**New scheduled task:** `expire_stale_requests` (every 15 min)

### Key design choices
- OTPs are 6-digit numeric strings, generated by `random.choices(string.digits, k=6)`
- Only SHA-256 hashes stored — plaintext never persists beyond the HTTP response
- Plaintext returned exactly once per successful `verify_unmask()` call
- `developer_mode=1` returns OTPs in plaintext for QA (`_dev_requester_otp`, `_dev_patient_otp`)

---

## 2026-04-13 — Phase 3E: Inpatient Dashboard

### Frappe Page
`medic_plus/medic_plus/page/inpatient_dashboard/` — visible to all practice roles + admin.

### APIs
- `get_inpatient_summary()` — four headline stats (current, today's admissions, expected discharges, avg LOS)
- `get_current_inpatients()` — full admitted-patient list with computed `los_days` and `current_ward`

Both gated by `@require_feature("inpatient_module")` — only Pro plan practices can access.

`_get_practice_filter()` returns `{}` for platform admins (see all) or `{"custom_practice": practice}` for practice staff.

---

## 2026-04-14 — Playwright UI Test Suite

44 tests across 4 files. All pass on staging (1 skipped when no inpatients are admitted).

Key lessons embedded in `CLAUDE.md` (Tests → UI Tests section):
- Scope locators to `.parent .child` not `get_by_text()` globally
- Use `urllib + CookieJar` for second-session permission tests
- Frappe 403 handler calls `error_callback()` with no args — `exc_type='ServerError'` is the signal, not "PermissionError" in the exception string

---

## 2026-04-22 — Phase 6: Doctor Self-Registration (OTP + Yoco)

- `/signup` funnel replaces `/register` and `/register/doctor`.
- Yoco webhook is the sole provisioning trigger (auto-provisions `provision_doctor` on `payment.succeeded`).
- Post-payment UX uses a signed one-time completion URL (12-hr TTL, SHA-256 hashed in Redis at rest) instead of Frappe's password reset.
- 15-min scheduler retries any PRR stuck in `Paid but not Provisioned`.
- `Registration Request` DocType dropped; orphan Users cleaned up by patch (System Users skipped and logged for manual review).
- Admin `onboard_doctor` refactored to share `provision_doctor` (now emits Company + POS + Checklist + Folder).

Production fixes surfaced by the E2E test:
- `_handle_payment_succeeded` runs as Administrator (Healthcare Practitioner.on_update needs User Permission insert; webhook signature is verified upstream so the elevation is safe).
- `complete.html` and `success.html` gate their immediate `frappe.call` on `whenFrappeReady` — the inline script runs before `frappe-web.bundle` is parsed.
- Form-handler errors use the `.then(success, error)` tuple form; `.catch` doesn't always fire on Frappe XHR rejections.

---

## 2026-04-30 — SA EMR Phase 1: Compliance core (#18)

Closes the legal-floor gap so the Daystar Health SPA can host real SA practice data. Six commits on `develop` (e51975c → d2b967a):

- New doctypes: `Patient Allergy` (FHIR-aligned criticality), `Patient Chronic Condition` (Link → Diagnosis), `Medical Aid Scheme` (CMS directory), `Record Archive Queue`. Each clinical doctype denormalises `custom_practice` from Patient on insert for fast PQC subqueries.
- 4 new Permission Query Conditions scope via `patient.custom_practice` + 1 PQC for `Patient Medical Record`. 12 Custom DocPerm rows (3 Practice roles × 4 doctypes — Receptionist read-only on chronic conditions).
- 4 SA medical-aid Custom Fields on `Patient Insurance Policy`: `custom_sa_scheme`, `custom_principal_member_id`, `custom_dependent_code`, `custom_authorisation_reference`.
- Whitelisted endpoints: `get_patient_allergies`, `get_patient_chronic_conditions`, `get_patient_medical_aid`, `search_icd10` — all assert patient ∈ active practice.
- `build_patient_summary` hydrates allergies (cap 50), chronic conditions (cap 50), medical aid (cap 5).
- Reference data fixtures: 1 `Code System` (ICD-10, FHIR uri), 34 curated WHO ICD-10 codes (HTN, T1/T2DM, asthma, URTI/UTI, depression/GAD, etc.), 10 SA schemes (Discovery, Bonitas, Momentum, Bestmed, Medshield, Profmed, Polmed, GEMS, Fedhealth, Keyhealth).
- Daily scheduler `medic_plus.api.retention.flag_overdue_records` — HPCSA Booklet 9 / NHA §17 (6-year retention, paediatric to age 21, idempotent via Record Archive Queue).
- SPA: Allergies + Conditions tabs in patient drawer, severe-allergy banner, Medical Aid card on Overview, reusable `MIcd10Picker` (250 ms debounced).
- Tests: 10 `IntegrationTestCase` (PQC shape, cross-practice blocks, happy-path reads, denormalisation, summary hydration), 4 retention tests (TDD), 4 Playwright (banner + tabs + ICD-10).

---

## 2026-05-02 — Phase 1E: Healthbridge Claims + POPIA Scaffold + FHIR R4 (#28)

Closing slice of Phase 1. Lands three verticals on `develop` in 8 atomic commits.

### Claims (Healthbridge real-time switching)

**New doctypes:**
- `Tariff Code` (autoname=field:code): BHF/SAMA procedure master; 20-code curated seed covering consultations, procedures, medications, dispensing fees; platform-admin R/W, practice roles read-only.
- `Switch Configuration` (autoname=field:practice): per-practice Healthbridge credentials (provider_code, endpoint_url, sender_id, username, encrypted password); PQC scoped by `practice` field.
- `Insurance Claim` (IC-.#####): Draft→Submitted→Accepted/Partial/Rejected/Error workflow; links practice, patient, encounter; has `claim_lines` child table.
- `Insurance Claim Line` (child table): line_type (Diagnosis/Procedure/Medication), code, description, quantity, unit_fee, total_fee, per-line status.

**Custom fields on Patient Encounter (Phase 1E):**
- `custom_section_claims` — collapsible section
- `custom_claim_diagnosis_code` (Data) — ICD-10 code (e.g. J01.9)
- `custom_claim_tariff_code` (Link → Tariff Code) — primary procedure
- `custom_claim_nappi_code` (Data) — NAPPI product code for primary medication

**Python modules:**
- `api/claim_builder.py`: pure function `build_claim(encounter_name)` → unsaved Insurance Claim. Reads the three Phase-1E encounter fields; hydrates scheme/member from Patient Insurance Policy; returns None for encounters with no claimable lines. No side-effects — table-testable.
- `api/healthbridge_client.py`: thin HTTP transport. `submit_to_switch(claim_name)` constructs Basic-Auth headers from Switch Configuration, builds JSON payload, POSTs to endpoint, parses per-line statuses from 200 response. `_post()` is a module-level callable — tests replace it without requests-mock at import time.
- `api/claims.py`: `@frappe.whitelist() submit_claim(claim_name)` — Draft→Submitted before network call (audit trace even on crash); applies Accepted/Partial/Error + per-line statuses; `get_claim_for_encounter(encounter_name)` lookup. `auto_build_claim_for_encounter()` idempotent helper called by `on_submit` hook.
- `doc_events.build_claim_on_submit()`: wired to `Patient Encounter.on_submit`.

**Tracer test** (`test_claims.py`, 12 IntegrationTestCase methods): Encounter submit auto-creates Draft claim with 3 lines (Diagnosis J01.9, Procedure 0190, Medication NAPPI 705793001); `submit_claim()` posts to monkeypatched `_post`, parses `HB-REF-9999` switch_reference, transitions to Accepted with per-line statuses; cross-tenant PQC blocks Practice B from reading/submitting Practice A's claim.

### POPIA Scaffold

**New doctypes:**
- `Patient Consent Record` (PCR-.#####): per-purpose (Treatment/Billing/Research/Marketing/AI/Insurance/PublicHealth/Legal/Other), versioned, POPIA s11 lawful basis, SHA-256 consent_text_hash, status lifecycle Given→Withdrawn/Expired/Pending. PQC: Practice roles scope via patient.custom_practice; Patient role sees own records only.
- `Sub-Processor Register` (autoname=field:processor_name): platform-wide DPA register; category (AI/Communications/Laboratory/HealthSwitching/Payments/Storage/Other); DPA signed date, annual review, cross-border transfer mechanism, breach SLA.

**Seeded sub-processors (10):** Anthropic (AI/USA), Jitsi (Communications/EU), LiveKit (Communications/USA), Healthbridge (HealthSwitching/SA), Lancet (Laboratory/SA), Ampath (Laboratory/SA), PathCare (Laboratory/SA), Vermaak (Laboratory/SA), NHLS (Laboratory/SA), NICD (Laboratory/SA — legal obligation basis for communicable disease reporting).

**Retention cron update:** `retention.flag_expired_consent_records()` — daily; marks Given consent records older than 3 years as Expired; idempotent; guards with `frappe.db.table_exists()` for migration safety.

### FHIR R4 Read-Only Emit

**New doctype:**
- `FHIR Access Token` (FAT-.#####): SMART v2 bearer tokens; SHA-256 hash only stored (raw never persisted); practice-bound; TTL 1 hour; PQC limits to issuing user + platform admins.

**Python modules:**
- `api/fhir/token.py`: `issue_token(user, practice, scope)` → (raw, doc_name); `resolve_token(raw)` validates hash + expiry; `revoke_token(raw)`.
- `api/fhir/mappers.py`: 6 FHIR R4/R5 resource mappers, all returning dicts that validate against `fhir.resources` models:
  - `Patient`: name (family/given), gender, DOB, SA-ID identifier, active flag.
  - `Encounter`: status (in-progress/discharged/cancelled), subject, participant, actualPeriod, diagnosis (ICD-10-ZA coded), type (BHF tariff coded). `meta.versionId` + `meta.lastUpdated` from Frappe `modified`.
  - `Condition`: from `custom_claim_diagnosis_code`, ICD-10-ZA coded, clinicalStatus=active.
  - `MedicationRequest`: from `custom_claim_nappi_code`, NAPPI coded, status=active, intent=order.
  - `AllergyIntolerance`: from Patient Allergy; SNOMED coded; criticality from severity.
  - `Observation` (vitals): BP (LOINC 55284-4 with systolic/diastolic components), body weight (29463-7), height (8302-2); UCUM units; encounter reference.
- `api/fhir/capability_statement.py`: builds CapabilityStatement listing 6 resource types; SMART-on-FHIR security tag; fhirVersion=4.0.1.
- `api/fhir/router.py`: `@frappe.whitelist()` endpoints — `get_metadata` (allow_guest), `get_patient`, `get_encounter`, `get_condition`, `get_medication_request`, `get_allergy_intolerance`, `get_observations`, `patient_everything` ($everything Bundle), `issue_fhir_token`. Cross-tenant: `_assert_resource_practice` compares resource's practice field to token's practice context; platform admins bypass. Session-user fallback for same-site SPA.
- `www/api/fhir/R4.py`: Frappe `www/` dispatcher; URL pattern `/api/fhir/R4/<ResourceType>/<id>`; returns `application/fhir+json`.
- `hooks.py`: `website_route_rules` entry for `/api/fhir/R4/<path:path>`.

**FHIR tracer test** (`test_fhir.py`, 24 IntegrationTestCase methods): token issue/resolve/expiry; Patient/Encounter/Condition/MedicationRequest/Observation all pass `fhir.resources` model_validate; CapabilityStatement validates with fhirVersion=4.0.1 and lists 6 resources; cross-tenant denial (Practice B token → DoesNotExistError on Practice A encounter); FHIR token PQC shape.

**Playwright UI tests** (`test_claims_fhir_ui.py`, 10 methods): FHIR metadata 200 with CapabilityStatement shape (no auth); claims API shape (null for unknown, error not crash, guest 401/403); token issuance requires login; sub-processor register >= 10 seeded rows including Healthbridge.

### Judgment calls and gaps

| Decision | Rationale |
|---|---|
| `fhir.resources` 8.2.0 (R5 model library) used to validate | Only available package; R4 JSON is structurally compatible; `fhirVersion: 4.0.1` declared in CapabilityStatement |
| Three flat custom fields on Encounter (not child table) | Minimal — avoids coupling to Healthcare module's internal drug_prescription schema until Phase 1D Drug Master lands |
| `_post` as module-level function | Allows monkeypatching without requests-mock at import time; cleaner than injecting a transport object |
| FHIR token TTL = 1 hour | Conservative for a healthcare context; operator can re-issue |
| Condition/MedicationRequest IDs include encounter name | Derived resources have no independent Frappe DocType; round-trip stable via encounter name |
| Issues #24, #26, #27 closed in code (not on GitHub) | Code exists (patient_identifier, encounter_order doctypes present); GitHub issue closure is a separate admin task |

### Unticked items (deferred)

- [ ] FHIR search (full `?patient=<id>` search across DB) — current router has stubs; full search needs pagination and SQL safety review
- [ ] FHIR SMART `/.well-known/smart-configuration` discovery document
- [ ] Drug Master from #27 — once merged, `medication_request_to_fhir` can reference Drug Master for richer FHIR coding
- [ ] FHIR write (CREATE/UPDATE) — read-only for Phase 1; write requires validation layer
- [ ] Structured SOAP encounter fields (#26) — `encounter_to_fhir` will map them when available

---

## 2026-05-09 — v2.1.0: Signup admin overrides (Force Provision + Mark Paid)

Closes the gap where a Practice Registration Request that pays out-of-band (or whose Yoco webhook was lost) had no admin path to completion. Two new System Manager-only whitelisted methods on `medic_plus.api.yoco`, surfaced as buttons on the PRR form:

- **`force_provision(request_name)`** — re-runs the canonical webhook path for a PRR that is already `payment_status="Paid"` but stuck before provisioning. Cherry-picked from earlier work on `feature/phase-7b-bulk-import` (commit `55bdf3b`); never previously merged to `develop`/`main`. Surfaced via a "Force Provision" button when the PRR is Paid + not yet provisioned.
- **`admin_mark_paid_and_provision(request_name, reason)`** — flips an Unpaid PRR to Paid (records `yoco_paid_at`, writes an audit Comment to the PRR timeline citing the actor and reason), then runs the same `_handle_payment_succeeded` path. Surfaced via a "Mark Paid (Admin Override)" button when the PRR is Unpaid + not yet provisioned. Reason is a required field on the dialog.

Both methods reuse `_handle_payment_succeeded` (which elevates to Administrator and calls `_provision_from_payment`) so the admin and webhook code paths produce byte-identical tenants. Idempotent for already-Paid requests; reject already-provisioned requests.

Side-effect from cherry-pick `55bdf3b`: `create_practitioner` and `create_practice` now persist the applicant's `mobile` to `Healthcare Practitioner.mobile_phone` and `Practice.phone` respectively (was being captured on the PRR + User but dropped during downstream provisioning).

**Tests** (10 new in `medic_plus/api/test_signup.py`): `TestForceProvision` (4) covers happy path on Paid, rejection of Unpaid, rejection of already-provisioned, System Manager guard. `TestAdminMarkPaidOverride` (6) covers happy path on Unpaid (assert payment flipped + provisioned + override flag true), audit-comment content, idempotence on already-Paid (override flag false), rejection of already-provisioned, System Manager guard, unknown-request rejection. Run via custom runner: `env/bin/python -m daystar_followup.tests._runner --site medic-demo-staging.thedaystar.co.za --module medic_plus.api.test_signup` (the bench runner trips over ERPNext's `BootStrapTestData` import on this site — same problem documented in `/home/CLAUDE.md` for crm-staging).

**Files**: `medic_plus/api/yoco.py` (force_provision + admin_mark_paid_and_provision), `medic_plus/api/_provisioning.py` (mobile propagation), `medic_plus/medic_plus/doctype/practice_registration_request/practice_registration_request.js` (new file — both buttons + Open Practice shortcut), `medic_plus/api/test_signup.py` (new test classes).

**Why now**: production saw a new PRR on medic-demo.thedaystar.co.za stuck in Unpaid with no admin escape hatch. v2.0.x had only the dev-only `_test_mark_paid` (gated on `developer_mode=1`) and the Yoco webhook itself.

---

## Roadmap

- [ ] Prescription print format — Jinja, per-practice letterhead ✅ Done (Phase 1D)
- [ ] Sick Note print format — Jinja, per-practice letterhead ✅ Done (Phase 1C)
- [x] Practice self-registration web form (scaffold at /register — full flow Phase 6)
- [x] Patient portal ✅ Done (Phase 3C)
- [x] Inpatient management dashboard ✅ Done (Phase 3E)
- [x] Subscription billing integration ✅ Done (Phase 3B)
- [ ] SMS/WhatsApp OTP option (Africa's Talking)
- [x] Unit tests ✅ Done (scattered across api/)
- [x] Playwright UI tests ✅ Done (Phase 3 hardening)
- [ ] Medical aid integration (Pro plan feature)
- [ ] Advanced reports (Pro plan feature)
- [ ] Phase 6 — Doctor self-registration approval flow
