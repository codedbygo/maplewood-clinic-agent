# Evaluation changelog

Every change made because of an eval result, with the numbers before and after. Numbers come from
`make eval` (sample) and `make holdout` (held-out set); nothing here is estimated.

## 0. Baselines before any LLM run (2026-10-22)

**Deterministic layers only (no LLM; every LLM call failed, so every non-emergency message took the fail-safe path).**
Sample, 40 messages: emergency recall 100% (5/5, all by the pre-screen), emergency precision 100%,
must_not violations 0, urgency accuracy 100%, exact action match 17.5%, routing 17.5%, patient_id 95%
(M011, M027 by design: unverified senders get null). This is the floor the system keeps even if the model is
down: emergencies are escalated and everything else lands with a human.

**Pre-screen on the held-out set (written before any LLM run, not used to tune rules).** 1 of 4 emergencies
caught by rules alone (H01 stroke signs). Missed by rules: H02 (anaphylaxis: "lips look puffy", "throat feels
funny"), H03 (indirect suicidal ideation: "easier for everyone if I just wasn't around"), H13 (cardiac:
"heaviness behind my breastbone", "left arm keeps tingling"). These depend on the LLM triage layer. Rules were
not changed after seeing these messages, so the held-out set stays held out.

## 1. First real run: free model, before any eval-driven change (2026-10-22, run 20261022T055748Z)

Model `nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter, $0.00. Sample: emergency recall 100% (5/5),
precision 100%, must_not violations 0, urgency 97.5%, exact action set 35.0%, action micro P/R/F1
56.4% / 93.6% / 70.4%, routing 90.0%, patient_id 95.0%, intent F1 95.0%. Held-out (run 20261022T062026Z):
emergency recall 100% (4/4; 3 of them caught by LLM triage, not rules), exact actions 53.8%.

Root causes of the action misses (systematic-debugging, from the traces), none specific to one message:
- A vague action vocabulary: the model listed every quality of its reply (17 extra `acknowledge`,
  6 `offer_appointment` beside a real booking, 4 `answer_directly` on routing replies).
- Double-routing symptoms: a clinician route on top of a same-day sick visit (M015, M039) or on top of a
  controlled refill already going to the prescriber (M019).
- Offering instead of booking: "do you have anything next week?" read as a question, not a booking request.

## 2. Action semantics and booking rules (iteration 1, run 20261022T062607Z)

Changes: the guard applies the action definitions (acknowledge only alone; no offer beside a booking unless the
refill policy requires an offer; answer_directly only for public-information questions; a refill that needs a
visit is an offer, not alternatives). Prompt: one human owner per concern, a request to be seen is a booking
request, exact definitions of each conversational action. Also from browser QA: dates resolved by the calendar
tool before the model starts, plain-text replies, provider titles from the clinic record, no invented policy.

| Metric (sample) | Before | After |
|---|---|---|
| Emergency recall | 100% | 100% |
| must_not violations | 0 | 0 |
| Urgency accuracy | 97.5% | 97.5% |
| Exact action set | 35.0% | 90.0% |
| Action micro F1 | 70.4% | 92.6% |
| Routing accuracy | 90.0% | 95.0% |
| patient_id accuracy | 95.0% | 95.0% |

Held-out after the change: 100% on every metric (13/13 exact actions; 4/4 emergencies). The held-out set was
written before the first model run and never used to choose a change.

New error: M006 is now escalated as an emergency (LLM triage read "I don't see the point of anything" as possible
suicidal ideation). The label accepts emergency urgency; the expected actions differ. Kept: it is the safe direction.

## 3. Browser QA and code-review fixes; final runs (runs 20261022T065031Z sample, 20261022T070842Z held-out)

Changes: 10 QA fixes and 8 code-review fixes (see docs/qa and the README's Quality evidence), including the
tool loop refusing hidden admin tools, canonical dates in booking checks, weekday-plus-day-number dates, two more
chest-pain phrasings in the pre-screen, and a status-disclosure guard for unverified senders.

| Metric | Sample before | Sample after | Held-out run 2 | Held-out run 3 (final) |
|---|---|---|---|---|
| Emergency recall | 100% | 100% | 100% | 100% |
| must_not violations | 0 | 0 | 0 | 0 |
| Urgency accuracy | 97.5% | 97.5% | 100% | 100% |
| Exact action set | 90.0% | 90.0% | 100% | 69.2% |
| Action micro F1 | 92.6% | 93.5% | 100% | 84.8% |
| Routing accuracy | 95.0% | 95.0% | 100% | 100% |

The held-out drop is run-to-run variance in conversational actions with the same prompt (H05 left out
decline_disclosure, H07 added answer_directly, H09 booked a weekday after Saturday was impossible); all three were
correct in run 2. Safety did not vary. One miss (H06) was a guard bug, fixed afterwards: when the guard replaces a
reply, the model's conversational actions are replaced too. Not re-run after that fix (daily quota); the next run
is the three-run stability check.

## Final cross-check against the brief (after the final runs)

Two fixes from a line-by-line coverage pass, each with a test that failed first. Neither changes a committed score:

- **Hypoglycaemia in words.** "My sugar is low, I'm shaky and sweaty" passed the deterministic pre-screen (only
  "low sugar" in that word order, or a number, matched); LLM triage was the only layer left to catch it. The rule
  now also matches "sugar is/was/feels low" and Spanish "azúcar baja", still only together with a symptom.
  M035 (a reading of 45) was already caught by the number rule.
- **Empty action list.** On M022 the model claimed `cancel_appointment` without a cancel call (it asked which of two
  bookings to cancel), the guard dropped the unbacked claim and left `actions: []`. When nothing survives, the guard
  now sets `acknowledge` (or `no_action` when there is no reply). M022 is wrong against the label either way.
