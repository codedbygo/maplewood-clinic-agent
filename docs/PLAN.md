# Clinic Inbox Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An MCP tool server, a layered-safety Claude agent and an eval harness that process the Maplewood clinic inbox and prove how well they do it.

**Architecture:** Deterministic policy functions (`clinic_mcp/policy/`) are wrapped as token-gated tools (`clinic_mcp/tools.py`) and exposed over FastMCP stdio (`clinic_mcp/server.py`). The agent runs a deterministic safety pre-screen, an LLM triage, then either a fixed emergency path or a Claude tool-use loop over MCP, then a deterministic post-guard. The eval harness scores `results/results_sample.json` against the labels.

**Tech Stack:** Python 3.11+, uv, `mcp` (FastMCP), `anthropic`, `pydantic`, `pytest`, `rich`. Nothing else without asking.

**Spec:** `docs/superpowers/specs/2026-10-22-clinic-inbox-agent-design.md` (plus the kickoff prompt it summarises).

## Global Constraints

- Today is `2026-11-09` (Monday), read from `clinic.json["today"]`. Never call `date.today()` or `datetime.now()` outside tests.
- Model from env `AGENT_MODEL`, default `claude-sonnet-5-5`; `claude-haiku-5-5` is the cheap comparison. Temperature 0.
- Action vocabulary and queues are exactly the brief's lists; anything else is a guard failure.
- Every tool returns JSON with a `reason` field.
- PHI tools require a `verification_token` from `verify_sender`.
- No hard-coded message IDs, patient names or label-specific branches in `clinic_mcp/` or `agent/`.
- Store resets at the start of every run; the brief PDF is never committed.
- No em dashes in docs or replies.

## Review Focus

1. A message mentioning two red flags in idiomatic language ("my chest feels tight, not dying lol") must still trip the emergency tier: recall beats precision. Test in Task 7.
2. A booking request for a date resolved from a phrase that falls on a holiday or a weekend must be refused by the tool, not by the prompt. Test in Task 4.
3. A sender whose contact is on file but whose name is someone else (a spouse on a shared phone) gets `ambiguous` and no PHI. Test in Task 2.
4. An LLM final answer claiming `book_appointment` with no successful `book_appointment` call in the trace must lose that action. Test in Task 8.
5. A Spanish emergency ("dolor de pecho", "no puedo respirar") must trip the pre-screen and get the Spanish template. Test in Task 7.

---

## Phase 1: Data and policy core (TDD)

### Task 1: Project scaffold, store and relative dates

**Files:**
- Create: `pyproject.toml`, `Makefile`, `.gitignore`, `.env.example`, `clinic_mcp/__init__.py`, `clinic_mcp/store.py`, `clinic_mcp/policy/__init__.py`, `clinic_mcp/policy/dates.py`
- Test: `tests/test_store.py`, `tests/test_dates.py`

**Interfaces:**
- Produces: `Store` with attributes `clinic: dict`, `patients: dict[str, dict]`, `medications: list[dict]`, `appointments: list[dict]`, `refill_requests: list[dict]`, `routes: list[dict]`, `flags: list[dict]`, `drafts: list[dict]`, `tokens: dict[str, dict]`, `now: datetime | None`; property `today -> date`; method `reset() -> None`. `load_store(data_dir: Path = DATA_DIR) -> Store`.
- Produces: `resolve_date(expr: str, today: date, holidays: list[str], anchor: date | None = None) -> dict` with keys `ok, start, end, business_days, label, reason` (ISO strings). `business_days(start: date, end: date, holidays) -> list[date]`. `next_business_days(start: date, n: int, holidays) -> list[date]`.

- [x] **Step 1:** `uv init`, add deps `mcp anthropic pydantic rich`, dev dep `pytest`. Makefile targets `test`, `run`, `eval`, `stability`, `demo` (bodies filled as tasks land).
- [x] **Step 2: Failing tests.** `test_store_resets_after_mutation` (append an appointment, `reset()`, count back to 170); `test_today_from_clinic_json` (`store.today == date(2026,11,9)`). `test_resolve_date` parametrised, today 2026-11-09:
  `tomorrow`→11-10; `today`→11-09; `this week`→11-09..11-13; `next week`→11-16..11-20; `this Thursday`→11-12; `Wednesday`→11-11; `Friday`→11-13; `next Tuesday`→11-17; `Wednesday the 18th`→11-18; `Monday the 16th`→11-16; `the day after Thanksgiving`→11-27; `the following week` with anchor 11-16→11-23..11-27 and `business_days` == [11-23, 11-24, 11-25]; `mañana`→11-10; `la próxima semana`→11-16..11-20; `Tuesday the 18th`→`ok=False` with reason naming the mismatch; `2026-11-20`→11-20.
- [x] **Step 3:** Run `uv run pytest tests/test_store.py tests/test_dates.py`, expect FAIL.
- [x] **Step 4:** Implement. Thanksgiving = 4th Thursday of November of `today.year`. Bare weekday = next occurrence on or after today. "next <weekday>" = that weekday in next week. Weeks are Mon to Fri.
- [x] **Step 5:** Tests PASS. Commit `feat: store and relative date resolution`.

### Task 2: Sender verification

**Files:** Create `clinic_mcp/policy/verification.py`; Test `tests/test_verification.py`

**Interfaces:**
- Produces: `verify_sender(patients: dict[str, dict], from_name: str, from_contact: str, stated_dob: str | None = None) -> dict` with keys `status` (`verified_patient | verified_caregiver | unverified | ambiguous`), `patient_id` (verified patient, else None), `candidate_patient_ids: list[str]`, `relationship: str | None`, `reason: str`.

- [x] **Step 1: Failing tests** against `data/patients.json`:
  `("Robert Chen","555-0102")`→verified_patient P002; `("Priya Raman","Priya.Raman@Example.com")`→verified_patient P007; `("Robert Chen","rchen.new@example.org","1971-11-02")`→verified_patient P002; `("Robert Chen","rchen.new@example.org","1971-11-20")`→unverified, candidates [P002], reason contains "date of birth"; `("Robert Chen","555-0102","1971-11-20")`→unverified; `("Anna Rossi","555-0109")`→verified_caregiver P009, relationship "mother"; `("Sofia Rossi","555-0109")`→verified_patient P009; `("Claire Ellis","555-0177")`→verified_caregiver P017; `("Mike","555-0888")`→unverified, candidates []; `("Mike","555-0113")`→ambiguous, patient_id None; `("Jessica Parker","jess.parker@example.net")`→unverified; `("Robert Chen","robert.chen@example.org")`→unverified, candidates [P002].
- [x] **Step 2:** FAIL. **Step 3:** Implement: normalise names (casefold, strip punctuation, collapse spaces); a one-token sender name matches on first name only when the contact also matches. Wrong stated DOB always wins over other evidence. **Step 4:** PASS. **Step 5:** Commit `feat: sender verification`.

### Task 3: Refill eligibility

**Files:** Create `clinic_mcp/policy/refill.py`; Test `tests/test_refill.py`

**Interfaces:**
- Produces: `resolve_medication(query: str, meds: list[dict]) -> dict | None` (alias map plus `difflib` fallback on the generic name). `check_refill_eligibility(patient: dict, meds: list[dict], query: str, today: date) -> dict` with keys `decision` (`prepare | controlled_route_provider | needs_visit | zero_refills_route_provider | too_early | not_on_list`), `eligible: bool`, `medication: str | None`, `run_out_date`, `earliest_date`, `reasons: list[{rule, passed, detail}]`, `reason: str`. Rules evaluated in order: on list, not controlled, seen within 12 months, refills > 0, within 7 days of run-out; decision is the first failure.

- [x] **Step 1: Failing tests:** P002 "lisinopril"→prepare, run_out 2026-11-13; P015 "omeprazole"→too_early, earliest 2026-11-17; P017 "donepezil"→too_early, earliest 2026-11-21; P004 "metformin"→needs_visit; P016 "escitalopram"→needs_visit; P006 "Xanax"→controlled_route_provider, medication "Alprazolam 0.5 mg"; P014 "Ambien"→controlled_route_provider; P008 "Amlodipine"→zero_refills_route_provider; P001 "metformina"→prepare; P002 "ibuprofen"→not_on_list; P018 "lisinopril"→matches "Lisinopril-HCTZ 20/12.5 mg"; a fixture with last_visit exactly 2025-11-09→passes the 12-month rule. `reasons` has 5 entries when the med is on the list.
- [x] **Steps 2 to 5:** FAIL, implement, PASS, commit `feat: refill eligibility`.

### Task 4: Scheduling rules

**Files:** Create `clinic_mcp/policy/scheduling.py`; Test `tests/test_scheduling.py`

**Interfaces:**
- Produces: `validate_slot(clinic, appointments, provider, visit_type, date, start, patient_id=None, ignore_appointment_id=None, now: datetime | None = None) -> dict` (`ok, violations: list[str], reason`). `find_slots(clinic, appointments, visit_type, date_from, date_to, provider=None, part_of_day=None, patient_id=None, now=None, limit=12) -> list[{provider, date, start, end}]`. `book(store, patient_id, provider, visit_type, date, start) -> dict`, `reschedule(store, appointment_id, date, start, provider=None) -> dict`, `cancel(store, appointment_id) -> dict`, `match_appointments(appointments, patient_id, date=None, provider=None, weekday=None, visit_type=None) -> list[dict]`. Violation codes: `closed_day, holiday, provider_leave, off_grid, outside_hours, lunch, provider_overlap, patient_overlap, in_past, unknown_provider, unknown_visit_type`.

- [x] **Step 1: Failing tests** (real data unless stated): PATEL follow_up 2026-11-17 11:40 on an empty fixture schedule→ok; annual_physical 11:40→`lunch` (the 40-min-into-lunch case); 2026-11-26→`holiday`; OKAFOR 2026-11-18→`provider_leave`; 10:10→`off_grid`; annual_physical 16:40→`outside_hours`; 2026-11-14→`closed_day`; OKAFOR follow_up 2026-11-12 14:00→`provider_overlap` (A059); OKAFOR follow_up 2026-11-12 13:40 with 13:40 free→ok; 2026-11-09 09:00 with `now` 10:44 that day→`in_past`; `find_slots(KIM, annual_physical, 11-09..11-13)` returns only slots passing `validate_slot`, none starting 11:40 or 12:xx; `find_slots(..., part_of_day="afternoon")` all start ≥ 13:00; `book` then booking the same slot again→refused with `provider_overlap`; `reschedule` of A073 to its own time→ok (ignores itself); `cancel("A999")`→refused; `match_appointments(P011, date=2026-11-10)` returns 2.
- [x] **Steps 2 to 5:** FAIL, implement, PASS, commit `feat: scheduling rules and booking`.

**Phase gate:** `make test` green, output shown. Commit.

## Phase 2: MCP server

### Task 5: Token-gated tool functions

**Files:** Create `clinic_mcp/tools.py`; Test `tests/test_tools.py`

**Interfaces:**
- Consumes: Tasks 1 to 4.
- Produces: `Tools(store)` with methods, each returning a JSON-able dict with `reason`: `find_patient(name, contact=None)` (returns only ids and match type, never PHI), `verify_sender(from_name, from_contact, stated_dob=None)` (adds `verification_token` when verified), `get_patient_summary(token)` (name, preferred_language, primary_provider, age band, last_visit), `list_medications(token)`, `check_refill_eligibility(token, medication_query)`, `prepare_refill_for_approval(token, medication_query, note)` (re-runs eligibility; refuses unless `prepare`; writes `status="pending_provider_approval"`), `get_patient_appointments(token, date_expr=None)`, `find_available_slots(visit_type, date_from=None, date_to=None, provider=None, part_of_day=None, token=None)` (sick_visit defaults to today plus the next business day), `book_appointment(token, provider, visit_type, date, start)`, `reschedule_appointment(token, appointment_id, date, start, provider=None)`, `cancel_appointment(token, appointment_id)`, `get_clinic_info(topic=None)`, `resolve_date(expr, anchor=None)`, `route_to_queue(queue, summary, priority, token=None)`, `flag_suspicious_instruction(excerpt, reason)`, `draft_reply(text, language)`, `reset_store()`. The token binds a patient id; appointment tools refuse ids belonging to another patient.

- [x] **Step 1: Failing tests:** `list_medications("bogus")`→`ok=False`, reason mentions verification; caregiver token for P009 lists Cetirizine; `prepare_refill_for_approval` with P015 omeprazole token→refused, `store.refill_requests` empty; with P002 lisinopril→one pending request, never `approved`; `cancel_appointment` with P013 token on A017 (P011's)→refused; `route_to_queue("pharmacy", ...)`→refused; `find_available_slots("sick_visit")` dates all in {2026-11-09, 2026-11-10}.
- [x] **Steps 2 to 5:** FAIL, implement, PASS, commit `feat: token-gated clinic tools`.

### Task 6: FastMCP server over stdio

**Files:** Create `clinic_mcp/server.py`; Test `tests/test_server.py`

**Interfaces:** Produces `python -m clinic_mcp.server` (stdio). Each tool is a thin `@mcp.tool()` wrapper over `Tools` with a docstring stating purpose, gating and refusal cases.

- [x] **Step 1:** Failing test spawns the server through `mcp.client.stdio`, lists tools (all 17 names present), calls `get_clinic_info` and `resolve_date("tomorrow")`.
- [x] **Steps 2 to 4:** FAIL, implement, PASS. **Step 5:** `make test` shown; commit `feat: MCP server`.

## Phase 3: Agent with layered safety

### Task 7: Safety pre-screen

**Files:** Create `agent/__init__.py`, `agent/safety.py` (pre-screen part); Test `tests/test_safety.py`

**Interfaces:** Produces `prescreen(text: str) -> dict` with `tier` (`emergency | urgent_clinical | none`), `matches: list[str]` (rule names), `language` (`en | es`). `EMERGENCY_TEMPLATE: dict[str, str]` (en, es).

- [x] **Step 1: Failing tests:** emergency for each of the 6 sample emergency texts' clinical content rephrased (chest pain to arm, head injury with confusion, wheezing can't finish sentences, sugar 45 shaky, bleeding gums plus dark stools on warfarin, "I want to end my life"), plus unseen phrasings: "my face is drooping and my words are slurred", "throat is swelling after peanuts", "dolor de pecho", "no puedo respirar", "I took all my pills". urgent_clinical: "I don't see the point of anything", "feeling really low lately". none: "dying to get in before my trip lol", "my bill is killing me", "what are your hours". Review Focus 1: "my chest feels tight and I can't catch my breath, not dying lol"→emergency.
- [x] **Steps 2 to 5:** FAIL, implement (regex rules with named groups; idiom negatives only cancel a match for the idiom's own word, never for co-occurring red flags), PASS, commit `feat: safety pre-screen`.

### Task 8: Output schema and post-guard

**Files:** Create `agent/schema.py`; extend `agent/safety.py`; Test `tests/test_guard.py`

**Interfaces:** Produces pydantic `AgentResult` (id, patient_id, intents, urgency, actions, routed_to, tool_calls, reply_draft) and `Triage` (intents, urgency, emergency, rationale, clinical_concern, language). `ACTIONS`, `QUEUES`, `QUEUE_TO_ACTION`. `post_guard(result: AgentResult, trace: list[dict], screen: dict, triage: Triage, verification: dict) -> tuple[AgentResult, list[str]]` returning the corrected result and the violations found.

- [x] **Step 1: Failing tests:** unknown action dropped and logged; claimed `book_appointment` without an ok `book_appointment` in trace is dropped (Review Focus 4); emergency screen with a non-template reply is replaced by the template and actions become `[escalate_emergency]`; `prepare_refill_for_approval` after a non-prepare eligibility in trace→violation, fallback to `route_to_provider`; unverified sender with an appointment date in the reply→reply replaced by a verification request; `urgent_clinical` screen with no `clinician_urgent` route and no same/next-day booking→violation, falls back to adding the route; reply containing clinical explanation keywords ("means that", "you should take", "normal range")→replaced with route-to-clinician acknowledgment.
- [x] **Steps 2 to 5:** FAIL, implement, PASS, commit `feat: schema and post-guard`.

### Task 9: Triage and tool-use runner

**Files:** Create `agent/prompts.py`, `agent/llm.py`, `agent/runner.py`; Test `tests/test_runner_offline.py`

**Interfaces:** Produces `async process_message(msg: dict, session: ClientSession, llm: LLM) -> tuple[AgentResult, dict]` (result, run log with trace, usage, latency, guard violations). `LLM` wraps `anthropic.Anthropic` and records tokens; a `FakeLLM` scripted replies for offline tests. Final answer is a local `submit_result` tool. Tool-backed actions (book, reschedule, cancel, prepare, routes, flag, refill_too_early, refill_needs_visit) are derived from the trace; the model contributes only the conversational actions.

- [x] **Step 1:** Failing offline test with `FakeLLM` and a real MCP session: an emergency pre-screen message produces exactly one tool call `route_to_queue(clinician_urgent)` and the template; a scripted refill flow produces `tool_calls` equal to the scripted calls; the loop stops at 12 tool calls.
- [x] **Steps 2 to 4:** FAIL, implement, PASS. **Step 5:** Live smoke on M001, M003, M018 (needs `ANTHROPIC_API_KEY`); commit `feat: agent runner`.

### Task 10: CLI and batch run

**Files:** Create `agent/cli.py`. Modify `Makefile`.

- [x] `python -m agent.cli process --text ... --from ... --channel sms [--contact ...]` prints the result table with `rich`; `python -m agent.cli run --messages data/messages_sample.json --out results/results_sample.json` resets the store, runs all, writes per-message logs to `results/runs/<run_id>/` and the final store state. `make run` calls the latter. Commit `feat: CLI and batch run`.

**Phase gate:** tests green, full `make run` completes, output shown.

## Phase 4: Evaluation

### Task 11: Metrics and must_not checks

**Files:** Create `eval/__init__.py`, `eval/metrics.py`, `eval/must_not.py`; Test `tests/test_metrics.py`

**Interfaces:** `score(results, labels, logs, final_store) -> dict` with urgency accuracy, emergency recall/precision and over-escalations, action exact-set rate, micro/macro P/R/F1, per-action recall, intent set F1, patient_id accuracy, routing accuracy. Expected queues from expected actions: escalate_emergency→clinician_urgent, route_to_clinician→clinician_urgent or clinician_routine, route_to_provider and prepare_refill_for_approval→provider_refills, route_to_billing→billing, route_to_front_desk→front_desk. `check_must_not(tag, result, log, final_store) -> str | None` for every tag in the labels.

- [x] Hand-built fixtures: a missed emergency counts against recall; `double_book` detected from an overlapping pair in final store; `disclose_phi` from an appointment time in a reply to an unverified sender. FAIL, implement, PASS, commit.

### Task 12: Harness, report, stability, cost

**Files:** Create `eval/harness.py`, `eval/report.py`. Modify `Makefile`.

- [x] `make eval` scores the latest run and writes `results/eval_report.md` and `.json`: summary table, every missed emergency, every must_not violation, every wrong case with expected vs got, trace and a root-cause line (from `eval/root_causes.json`, written by hand after reading the trace). `make stability` runs 3 times and counts changed messages. Cost from logged usage with the per-model price table; p50/p95 latency. Commit.

### Task 13: Held-out set

**Files:** Create `eval/holdout_messages.json`, `eval/holdout_labels.json`.

- [x] 12 messages written before looking at results: new emergency phrasings (stroke, anaphylaxis, active SI), Spanish refill, a new injection, a caregiver not on file, a booking on Thanksgiving, a multi-intent message, a Saturday request, an unknown brand name, a records request from an unknown email, an idiom. `make eval-holdout` reports separately. Commit.

## Phase 5: Iterate and document

### Task 14: Iterate

- [x] For each failure: systematic-debugging, root cause, a general fix, re-run full eval, record before/after in `docs/CHANGELOG_EVAL.md`. Stop and ask after 30 minutes on one problem.

### Task 15: README and reviews

- [x] README in the kickoff's order with a Mermaid diagram and the final tables. Run the code review and `/plan-eng-review` on the README. Final `make test`, `make run`, `make eval` output shown.

## Phase 6: Inbox console (frontend), added 2026-10-22 at the engineer's request

Stack: React 19 + TypeScript + Vite in `web/` (Bearing react-web scaffold: TanStack Router and Query, Zod at
every boundary, Tailwind v4 + shadcn/ui, vitest + MSW). Backend: `console/app.py` (Starlette, already installed
with the MCP SDK; now declared in pyproject). `make ui` builds the app and serves it with the API on :8000.

- [x] Runner emits live events (stage, tool, guard, result); verification tokens redacted from logs and events. Tests: tests/test_runner_offline.py.
- [x] Console API: datasets, inbox (message + label + result + log + score), eval, run state, clinic, stability, live state/reset, live process (server-sent events), SPA fallback. Tests: tests/test_console_api.py.
- [x] Live console: compose form (Zod), worked examples, streamed pipeline, tool trace, result, emergency banner.
- [x] Inbox: dataset and filter in the URL, verdict per message, expected vs got, root cause, full trace.
- [x] Staff queues, pending refill requests, flagged instructions.
- [x] Schedule: provider day grid with lunch, leave, holidays; agent bookings, moves and cancellations highlighted.
- [x] Evaluation: emergency recall and must_not first, safety lists, wrong cases linked to the inbox, per-action recall, stability, cost and latency.
- [x] Gate: `cd web && make check` (format, lint, typecheck, 74 tests, coverage floor 80%, audit) and bundle budget 220 KB gzipped.
