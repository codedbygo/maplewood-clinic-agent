# Clinic inbox agent: design

Date: 2026-10-22. Source: the Edvak Forge brief and the kickoff prompt. This file records the
design as decided and the calls made during brainstorming.

## Intent

An AI agent that works the Maplewood Family Clinic inbox: it understands each message, acts through
an MCP tool server over the clinic data, and escalates to humans. It is graded on safety first, then
on measured reliability, tool design, judgement and clear explanation.

## Goals

- 100% emergency recall on the 40 sample messages, with a structure that makes a miss unlikely:
  a deterministic pre-screen sets a floor the LLM cannot lower.
- Policy in code: every date calculation, eligibility rule, slot check and verification decision
  is a deterministic tool that returns structured reasons.
- An honest evaluation: every metric reproducible with `make eval`, every failure listed.
- Generalisation to unseen messages, shown on a held-out set I write myself.

## Non-goals

- MongoDB, a web UI, sending real messages, persistence across runs.
- Clinical answers of any kind.

## Anti-goals (a failure even if it "works")

- Any hard-coded message ID, patient name or label-specific branch.
- Prompt-only enforcement of a rule that a tool or guard could enforce.
- Reporting a number that was not produced by a command in the repo.

## Architecture (decided in the kickoff)

1. Deterministic safety pre-screen (`agent/safety.py`).
2. LLM triage with structured output (intents, urgency, emergency + rationale).
3. Emergency path: route to `clinician_urgent`, fixed template reply, no other work.
4. Normal path: Claude tool-use loop over MCP tools (stdio), capped at 12 tool calls.
5. Deterministic post-guard; on failure, fall back to a safe result and log why.
6. Output in the brief's schema; `tool_calls` taken from the real trace.

PHI tools require a `verification_token` from `verify_sender`. Store is in memory, reset per run.
Today is fixed at 2026-11-09 from `clinic.json`; the system clock is never used.

## Calls made during brainstorming (mine, open to override)

1. **Two-tier safety pre-screen.** Tier `emergency` (hard floor, emergency path): cardiac, respiratory,
   stroke, head injury with confusion, hypoglycaemia with symptoms, bleeding on an anticoagulant,
   anaphylaxis, active suicidal ideation, a plan, self-harm, "better off dead", "don't want to be
   here". Tier `urgent_clinical` (floor: urgency at least `urgent`, a `clinician_urgent` route is
   required, the normal path still runs): passive hopelessness and low mood, other worrying symptoms.
   The LLM triage can raise either tier, never lower it.
2. **`patient_id` is null for unverified senders**, as the brief says. M011 and M027 are labelled
   with the patient the message concerns; these are reported as known label disagreements.
3. **Not seen in 12 months: always `refill_needs_visit` + `offer_appointment` + `route_to_provider`**,
   as `refill_policy` says. M004's label omits the route; reported.
4. **Ambiguous target appointments are never guessed.** If more than one booking matches, the
   cancel/reschedule tools refuse with the candidates and the agent asks which one. M022 (two
   bookings tomorrow) is reported if it misses.
5. **A same-day or next-business-day sick visit satisfies "urgent concern reaches a clinician"**,
   so the guard does not add `route_to_clinician` on top of a booking (M015, M039).
6. **Caregiver verification.** `authorised_caregiver` is `{name, relationship, phone}`. A contact match
   verifies the sender as the patient when the sender name matches the patient, and as the caregiver
   when it matches the caregiver name. If the contact matches but the name matches neither, the
   sender is `ambiguous` and gets no PHI. A stated DOB that does not match makes the sender
   unverified even if the name matches.
7. **Sick-visit provider choice.** Prefer the patient's primary provider; if none is free within 1
   business day, offer any provider who sees the patient's age group.
8. **Repository.** This folder gets its own git repo (the home directory is itself a repo). The brief
   PDF is confidential and is not committed.

## Left to the builder

Tool argument shapes, prompt wording, the exact red-flag pattern list (biased to recall, each pattern
unit-tested, including idiom negatives such as "dying to get in").
