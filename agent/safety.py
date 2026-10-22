"""Deterministic safety layers around the LLM.

prescreen(): red-flag rules run on every message before the LLM sees it. Its tier is a floor:
the LLM can raise urgency, never lower it. Rules are biased to recall: a false alarm costs a
clinician a minute, a miss can cost a life. Two consequences, both deliberate:
  * negation never cancels an emergency rule ("no chest pain but my arm is numb" still fires);
  * idioms are removed as phrases before matching, so "dying to get in lol" is ignored but a real
    red flag elsewhere in the same message still fires.

post_guard(): validates the final result against the policy before it is emitted (see bottom).
"""

from __future__ import annotations

import re
import unicodedata

EMERGENCY_TEMPLATE = {
    "en": "Please call 911 now or go to the nearest emergency department. "
    "Our clinical team has been alerted to your message.",
    "es": "Por favor, llame al 911 ahora o vaya al departamento de emergencias más cercano. "
    "Nuestro equipo clínico ha sido alertado sobre su mensaje.",
}


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower().replace("’", "'"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("'", "")
    return re.sub(r"\s+", " ", text)


IDIOMS = [
    r"dying (to|for)\b", r"to die for", r"\b(is|are|was|were|s) killing me", r"killed it",
    r"dead (tired|on my feet)", r"could (have )?die(d)? of \w+", r"g[ai]ve me a heart attack",
    r"\b(fell|fall|falling) (behind|asleep)", r"bleeding me dry",
]

ANTICOAGULANTS = (r"warfarin|coumadin|jantoven|eliquis|apixaban|xarelto|rivaroxaban|pradaxa|dabigatran|heparin|"
                  r"enoxaparin|lovenox|blood thinner|anticoagul\w*|clopidogrel|plavix")

# (name, tier, pattern). Co-occurrence rules are functions below.
RULES: list[tuple[str, str, str]] = [
    ("chest_pain", "emergency",
     r"\bchest\b.{0,30}\b(pain\w*|pressure|tight\w*|crush\w*|heav\w*|hurt\w*|squeez\w*|ache|aching)\b"
     r"|\b(crush\w*|heavy|tight\w*|squeez\w*|sharp|pressure)\b.{0,20}\bchest\b|\bheart attack\b"
     r"|dolor (de|en el) pecho|presion en el pecho|duele\w*\s+(mucho\s+)?(el\s+)?pecho|pecho\b.{0,20}\bduele"),
    ("breathing", "emergency",
     r"\b(cant|cannot|can not|unable to|struggling to|hard to|trouble|difficulty|difficult to) "
     r"(breathe|breathing|catch (my|his|her|their) breath)\b|short(ness)? of breath|\bcant finish (a |my )?sentences?"
     r"|\bgasping\b|\b(not|stopped) breathing\b|no puedo respirar|me falta (el )?aire|\b(lips|face) (are |is )?(turning )?blue\b|\bchoking\b"),
    ("severe_asthma", "emergency", r"wheez\w*.{0,60}(not helping|isnt helping|isnt working|not working|cant|worse|severe)"
     r"|(not helping|isnt helping|isnt working|not working).{0,60}wheez"),
    ("stroke_signs", "emergency",
     r"\b(face|smile) (is )?(\w+ )?droop\w*|\bdroop\w* (face|smile)|slurr\w* (speech|words)|(speech|words) (are |is )?slurr\w*"
     r"|\bslurring\b|\bstroke\b|sudden(ly)? (\w+ ){0,2}(numb\w*|weak\w*|confus\w*|vision|blind\w*|cant (speak|talk|see|move))"
     r"|\bcant (move|feel) (my |his |her )?(arm|leg|face|side)|worst headache"),
    ("unresponsive_or_seizure", "emergency",
     r"\bunresponsive|unconscious|pass(es|ed)? out|faint(ed|ing)?\b|seizure|convuls\w*|(wont|cant|not) wak\w*|no responde|desmay\w*"),
    ("severe_bleeding", "emergency",
     r"(vomit\w*|cough\w*|throw\w*) (up )?blood|blood in (my |his |her )?(stool|poop|vomit)|bloody (stool|poop|vomit)"
     r"|(black|dark|tarry) (stool|poop)s?|\btarry\b|(wont|doesnt|cant|will not) stop bleeding|bleeding (wont|doesnt|will not) stop"
     r"|bleeding heavily|heavy bleeding|bleeding a lot|a lot of blood"),
    ("anaphylaxis", "emergency",
     r"(throat|tongue|lips?|face|mouth) (is |are |feels? )?(\w+ )?(swell\w*|swollen|closing)|swell\w* (of )?(my |the |his |her )?(throat|tongue|lips?)"
     r"|throat (is |feels )?(tight\w*|closing)|anaphyla\w*|epi ?pen|(allergic reaction|hives).{0,60}(breath|throat|swell|wheez|dizz|faint)"),
    ("self_harm", "emergency",
     r"\bkill\w* (my ?self|myself)|suicid\w*|end (my life|it all)|take my (own )?life|want(ed)? to die|wish i (was|were) dead"
     r"|better off (dead|without me)|better off if i (was|were|wasnt|werent) (dead|gone|here|around)"
     r"|(dont|do not) want to (be here|live|be alive|wake up)|no reason to (live|go on)"
     r"|(hurt\w*|harm\w*|cut|cutting|burn\w*) (my ?self|myself)|self[- ]?harm|overdos\w*"
     r"|took (all|a bunch|too many|a whole bottle|a handful)( of)?( my)? (pills|meds|tablets|medication)"
     r"|quiero morir|matarme|quitarme la vida|no quiero vivir|hacerme dano|no (tengo )?ganas de vivir"),
    ("low_mood", "urgent_clinical",
     r"dont see the point|no point (in|to) (anything|living|life|going on)|hopeless\w*"
     r"|(feel\w*|felt) (\w+ ){0,2}(low|down|depressed|empty|worthless|hopeless)|\bdepress(ed|ion)\b|cant (cope|go on)|worthless"
     r"|deprimid\w*|sin esperanza|panic attack"),
    ("fever", "urgent_clinical", r"\bfever\w*|temperature of|\bfiebre\b"),
    ("wheezing", "urgent_clinical", r"wheez\w*"),
    ("head_bump", "urgent_clinical", r"\b(hit|bump\w*|bang\w*|struck|injur\w*) (\w+ ){0,2}head|head (injury|trauma)|\bfell\b|\bfall\b|concussion|se cayo"),
    ("bleeding", "urgent_clinical", r"\bbleed\w*|\bbled\b|sangr\w*"),
    ("allergic_reaction", "urgent_clinical", r"allergic reaction|reaccion alergica|\bhives\b"),
    ("new_confusion", "urgent_clinical", r"\b(seems?|is|was|became|getting|acting|very|new) confus\w*"),
    ("severe_pain", "urgent_clinical", r"(severe|unbearable|excruciating|worst) (\w+ ){0,2}pain|pain (is )?(10|ten)( ?/ ?10| out of 10)"),
    ("pregnancy_concern", "urgent_clinical", r"pregnan\w*|embarazada"),
]
_COMPILED = [(n, t, re.compile(p)) for n, t, p in RULES]
NEGATED_URGENT = [r"\bno fever\w*", r"without (a )?fever", r"\bno fiebre", r"sin fiebre", r"fever (is )?(gone|broke)"]

HYPO_SYMPTOMS = r"shak\w*|sweat\w*|confus\w*|dizz\w*|faint\w*|trembl\w*|tembl\w*|sud\w*|clammy|blurr\w*"
SUGAR = re.compile(r"\b(blood sugar|sugars?|glucose|bg|bs|azucar|glucosa)\b[^0-9]{0,25}(\d{2,3})")


def _co_occurrence(t: str) -> list[tuple[str, str]]:
    out = []
    head = re.search(r"\b(hit|bump\w*|bang\w*|struck|injur\w*) (\w+ ){0,2}head|head (injury|trauma)|\bfell\b|\bfall\b|concussion|se cayo", t)
    if head and re.search(r"confus\w*|vomit\w*|throw\w* up|disoriented|not making sense|drows\w*|confundid\w*", t):
        out.append(("head_injury_with_confusion", "emergency"))
    if re.search(ANTICOAGULANTS, t) and re.search(r"\bbleed\w*|\bbled\b|\bblood\b(?! (pressure|sugar|test|work|draw))|bruis\w*|sangr\w*", t):
        out.append(("bleeding_on_anticoagulant", "emergency"))
    if re.search(r"pregnan\w*|embarazada", t) and re.search(r"\bbleed\w*|cramp\w*|severe pain|sangr\w*", t):
        out.append(("pregnancy_bleeding", "emergency"))
    for m in SUGAR.finditer(t):
        value = int(m.group(2))
        if value < 55 or (value < 70 and re.search(HYPO_SYMPTOMS, t)):
            out.append(("hypoglycaemia", "emergency"))
        elif value < 70 or value >= 400:
            out.append(("glucose_out_of_range", "urgent_clinical"))
    if re.search(r"low (blood )?sugar|hypo\b|hypoglyc\w*", t) and re.search(HYPO_SYMPTOMS, t):
        out.append(("hypoglycaemia", "emergency"))
    return out


SPANISH_WORDS = {"hola", "necesito", "por", "favor", "tengo", "una", "cita", "para", "mi", "que", "el", "la", "los", "las",
                 "de", "con", "gracias", "quiero", "tienen", "algo", "proxima", "semana", "dolor", "mas", "puedo", "estoy",
                 "muy", "es", "y", "mama", "hijo", "hija", "receta", "medicina", "manana", "ayuda", "buenos", "dias", "usted",
                 "duele", "mucho", "pecho", "brazo", "izquierdo", "derecho", "desde", "anoche", "hola", "necesito"}


def detect_language(text: str) -> str:
    raw = (text or "").lower()
    words = re.findall(r"[a-z]+", normalise(text))
    if not words:
        return "en"
    score = sum(w in SPANISH_WORDS for w in words) + 2 * len(re.findall(r"[ñáéíóú¿¡]", raw))
    return "es" if score >= 2 and score / len(words) >= 0.25 else "en"


def prescreen(text: str) -> dict:
    t = normalise(text)
    # "my chest is killing me" is a symptom, not an idiom: keep the body part's meaning before idioms go.
    t = re.sub(r"\b(chest|heart|head|stomach|belly|abdomen)\s+(is|s|was|has been)\s+killing me", r"\1 pain", t)
    for idiom in IDIOMS:
        t = re.sub(idiom, " ", t)
    matches: list[tuple[str, str]] = []
    for name, tier, rx in _COMPILED:
        target = t
        if tier == "urgent_clinical":
            for neg in NEGATED_URGENT:
                target = re.sub(neg, " ", target)
        if rx.search(target):
            matches.append((name, tier))
    matches += _co_occurrence(t)
    tiers = {tier for _, tier in matches}
    tier = "emergency" if "emergency" in tiers else "urgent_clinical" if tiers else "none"
    return {
        "tier": tier,
        "matches": sorted({n for n, _ in matches}),
        "language": detect_language(text),
    }


# ---------------------------------------------------------------------------
# Post-guard
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field  # noqa: E402

from agent.schema import (  # noqa: E402
    ACTIONS, CONVERSATIONAL_ACTIONS, DECISION_TO_ACTION, DECISIONS_NEEDING_PROVIDER, INTENTS, QUEUE_TO_ACTION,
    TOOL_ACTIONS, URGENCIES, AgentResult, FinalAnswer,
)

FALLBACK_REPLIES = {
    "ack": {
        "en": "Thank you for your message. A member of our team will review it and get back to you.",
        "es": "Gracias por su mensaje. Un miembro de nuestro equipo lo revisará y se comunicará con usted.",
    },
    "verify": {
        "en": "Thank you for your message. Before we can share or act on any personal health information, we need to "
              "verify your identity. Please reply with the patient's full name and date of birth, or contact us from "
              "the phone number or email we have on file.",
        "es": "Gracias por su mensaje. Antes de compartir o gestionar información de salud personal, necesitamos "
              "verificar su identidad. Responda con el nombre completo y la fecha de nacimiento del paciente, o "
              "contáctenos desde el teléfono o correo electrónico que tenemos registrado.",
    },
    "clinician": {
        "en": "Thank you for your message. We have passed it to our clinical team, who will follow up with you. "
              "If your symptoms get worse or you think this is an emergency, call 911 or go to the nearest emergency department.",
        "es": "Gracias por su mensaje. Lo hemos enviado a nuestro equipo clínico, que se comunicará con usted. "
              "Si sus síntomas empeoran o cree que es una emergencia, llame al 911 o vaya al departamento de emergencias más cercano.",
    },
    # Names nobody, so it can never confirm that a person is a patient here.
    "decline": {
        "en": "Thank you for your message. To protect privacy, we can't share any information about another person, "
              "including whether they are a patient with us. The person can contact us directly, or an authorised "
              "caregiver on file can reach us from the phone number we have on record.",
        "es": "Gracias por su mensaje. Para proteger la privacidad, no podemos compartir información sobre otra persona, "
              "ni siquiera si es paciente nuestro. La persona puede comunicarse con nosotros directamente, o un cuidador "
              "autorizado registrado puede contactarnos desde el teléfono que tenemos en el expediente.",
    },
}

# Policy-sounding claims (notice periods, fees) that no tool returns. Flagged for review, not rewritten:
# deleting sentences automatically would be riskier than the claim.
UNSUPPORTED_POLICY = re.compile(
    r"\b\d+\s*(?:hours?|hrs?|horas|days?|d[ií]as)\b[^.\n]{0,40}\b(?:notice|in advance|advance|antelaci[oó]n|anticipaci[oó]n)\b"
    r"|\b(?:notice|antelaci[oó]n)\b[^.\n]{0,30}\b\d+\s*(?:hours?|horas)\b"
    r"|\$\s?\d+[^.\n]{0,30}\b(?:fee|charge|cargo)\b|\b(?:late|cancellation|no-show)\s+fee\b",
    flags=re.IGNORECASE,
)


# Phrases that confirm someone is a patient or has visits, which an unverified sender must never get.
STATUS_DISCLOSURE = re.compile(
    r"\b(?:is|are)\s+(?:registered|a patient|our patient|on file|scheduled|booked)\b"
    r"|\b(?:has|have)\s+(?:an?\s+|any\s+)?(?:appointment|visit)s?\b|\b(?:her|his|their)\s+(?:appointment|visit|schedule)s?\b"
    r"|\b(?:es|est[aá])\s+(?:registrad[oa]|paciente)\b|\btiene\s+(?:una\s+)?cita\b",
    flags=re.IGNORECASE,
)


def plain_text(reply: str) -> str:
    """Replies go out by SMS and portal as plain text: drop Markdown emphasis and heading marks."""
    reply = re.sub(r"(\*\*|__)(.+?)\1", r"\2", reply)
    return re.sub(r"(?m)^#{1,6}\s+", "", reply)


def correct_provider_titles(reply: str, providers: list[str]) -> str:
    """A provider whose name on file has no "Dr." (a nurse practitioner) is never called Dr. in a reply."""
    for full in providers:
        if full.startswith("Dr"):
            continue
        name = full.split(",")[0].strip()
        first, last = name.split()[0], name.split()[-1]
        reply = re.sub(rf"\bDra?\.?\s+(?:{re.escape(first)}\s+)?{re.escape(last)}\b(?:,\s*NP\b)?", full, reply)
    return reply

# Phrases that signal the reply is explaining or advising clinically. Narrow on purpose: routing,
# booking and refill confirmations must not trip it.
CLINICAL_ADVICE = re.compile(
    r"\bmeans that\b|\bmeans (your|you)\b|\bis caused by\b|\bindicates\b|\bis a sign of\b|\bsounds like (a|an|you)\b"
    r"|\bcould be (a|an) \w+ (infection|condition|reaction)|\byou should (take|stop|increase|decrease|double|skip|try|use)\b"
    r"|\btry (taking|using|drinking)\b|\bnormal range\b|\btake \d+ ?(mg|mcg|tablets?|pills?)\b|\bdrink (plenty|lots)\b"
    r"|\b(ibuprofen|tylenol|acetaminophen|advil|motrin|aspirin|benadryl)\b|\bover[- ]the[- ]counter\b|\bhome remed"
    r"|\bsignifica que\b|\bdebe tomar\b"
)


@dataclass
class GuardOutcome:
    result: AgentResult
    violations: list[str] = field(default_factory=list)
    extra_routes: list[dict] = field(default_factory=list)


def _ordered(actions) -> list[str]:
    s = set(actions)
    return [a for a in ACTIONS if a in s]


def _max_urgency(a: str, b: str) -> str:
    return min(a, b, key=URGENCIES.index)


def post_guard(message_id: str, answer: FinalAnswer, trace: list[dict], screen: dict, verification: dict,
               context: dict) -> GuardOutcome:
    """Validate and correct the final result. Pure: side effects (extra routes) are returned to the runner."""
    v: list[str] = []
    extra: list[dict] = []
    lang = "es" if context.get("language", screen.get("language")) == "es" else "en"

    ok_calls = [c for c in trace if c.get("ok")]
    explicit_routes = [(c["input"].get("queue"), c["input"].get("priority", "routine")) for c in ok_calls if c["name"] == "route_to_queue"]
    queues = [q for q, _ in explicit_routes] + ["provider_refills" for c in ok_calls if c["name"] == "prepare_refill_for_approval"]
    draft_texts = [c["input"].get("text", "") for c in ok_calls if c["name"] == "draft_reply"]
    reply = draft_texts[-1] if draft_texts else ""
    if reply:
        cleaned = correct_provider_titles(plain_text(reply), context.get("providers", []))
        if cleaned != reply:
            v.append("reply normalised: plain text and provider titles from the clinic record")
        reply = cleaned
        for m in UNSUPPORTED_POLICY.finditer(reply):
            v.append(f"unsupported policy claim in reply (no tool states it): '{m.group(0)}'")
    decisions = [c["output"].get("decision") for c in trace if c["name"] in ("check_refill_eligibility", "prepare_refill_for_approval")]
    decisions = [d for d in decisions if d]

    # 1. Actions: tool-backed from the trace, conversational from the model.
    derived = {TOOL_ACTIONS[c["name"]] for c in ok_calls if c["name"] in TOOL_ACTIONS}
    for q, prio in explicit_routes:
        derived.add("escalate_emergency" if q == "clinician_urgent" and prio == "emergency" else QUEUE_TO_ACTION[q])
    derived |= {DECISION_TO_ACTION[d] for d in decisions if d in DECISION_TO_ACTION}
    actions = set(derived)
    for a in answer.actions:
        if a not in ACTIONS:
            v.append(f"unknown action '{a}' dropped")
        elif a in CONVERSATIONAL_ACTIONS:
            actions.add(a)
        elif a not in derived:
            v.append(f"model claimed '{a}' but no successful tool call backs it; dropped")

    # 2. Refill policy outcomes that require a provider route and an offered visit.
    if any(d in DECISIONS_NEEDING_PROVIDER for d in decisions) and "provider_refills" not in [q for q, _ in explicit_routes]:
        extra.append({"queue": "provider_refills", "priority": "routine", "summary": "Refill needs provider action (policy decision: "
                      + ", ".join(sorted({d for d in decisions if d in DECISIONS_NEEDING_PROVIDER})) + ")."})
        actions.add("route_to_provider")
        v.append("refill decision required a provider route; added")
    if "needs_visit" in decisions:
        actions.add("offer_appointment")

    # 3. Intents and urgency, with the deterministic floor.
    intents = [i for i in answer.intents if i in INTENTS]
    for i in set(answer.intents) - set(INTENTS):
        v.append(f"unknown intent '{i}' dropped")
    urgency = answer.urgency if answer.urgency in URGENCIES else "routine"
    emergency = screen["tier"] == "emergency" or answer.emergency or context.get("llm_emergency", False) or "escalate_emergency" in actions
    if screen["tier"] == "urgent_clinical":
        urgency = _max_urgency(urgency, "urgent")

    patient_id = verification.get("patient_id") if str(verification.get("status", "")).startswith("verified") else None

    if emergency:
        if urgency != "emergency":
            v.append(f"urgency raised from '{urgency}' to emergency by safety floor")
        urgency = "emergency"
        did_work = [c["name"] for c in ok_calls if c["name"] in ("prepare_refill_for_approval", "book_appointment", "reschedule_appointment", "cancel_appointment")]
        if did_work:
            v.append(f"clinical/admin work done on an emergency message: {did_work}")
        if ("clinician_urgent", "emergency") not in explicit_routes:
            extra.append({"queue": "clinician_urgent", "priority": "emergency", "summary": "Possible emergency: " + ", ".join(screen.get("matches") or ["flagged by triage"])})
            v.append("emergency without clinician_urgent escalation; added")
        if reply not in EMERGENCY_TEMPLATE.values():
            if reply:
                v.append("emergency reply was not the fixed template; replaced")
            reply = EMERGENCY_TEMPLATE[lang]
        actions = {"escalate_emergency"}
        if "clinical" not in intents:
            intents.append("clinical")
    else:
        # 4. Urgent clinical concern must reach a clinician today (a same/next-business-day visit counts).
        if screen["tier"] == "urgent_clinical":
            soon = {context.get("today"), context.get("next_business_day")} - {None}
            booked_soon = any(c["name"] in ("book_appointment", "reschedule_appointment") and c["output"].get("appointment", {}).get("date") in soon
                              for c in ok_calls)
            if ("clinician_urgent" not in [q for q, _ in explicit_routes]) and not booked_soon:
                extra.append({"queue": "clinician_urgent", "priority": "urgent",
                              "summary": "Clinical concern in message: " + ", ".join(screen.get("matches", []))})
                actions.add("route_to_clinician")
                v.append("urgent clinical concern without a same-day clinician route; added")

        # 5. No clinical explanations or advice in automated replies.
        if reply and CLINICAL_ADVICE.search(normalise(reply)):
            v.append("reply contained clinical explanation/advice; replaced and routed to a clinician")
            reply = FALLBACK_REPLIES["clinician"][lang]
            actions.discard("answer_directly")
            if "route_to_clinician" not in actions:
                actions.add("route_to_clinician")
                extra.append({"queue": "clinician_routine" if urgency == "routine" else "clinician_urgent",
                              "priority": urgency, "summary": "Clinical question needs a clinician."})

        # 6. Privacy for unverified senders. First, specific details of a candidate patient (dates, times,
        #    medications) mean "verify first". Then any reply that names another patient or confirms someone's
        #    status gets the neutral decline (naming someone in a decline still confirms they are known here).
        templates = {t for v in FALLBACK_REPLIES.values() for t in v.values()}
        if patient_id is None and reply:
            low = reply.lower()
            leaked = [t for t in context.get("phi_terms", []) if t and t.lower() in low]
            if leaked:
                v.append(f"possible PHI disclosed to unverified sender ({leaked}); reply replaced")
                reply = FALLBACK_REPLIES["verify"][lang]
                actions -= {"answer_directly", "book_appointment", "offer_appointment"}
                actions.add("request_verification" if verification.get("candidate_patient_ids") else "decline_disclosure")
        if patient_id is None and reply and reply not in templates:
            named = [n for n in context.get("other_patient_names", []) if re.search(rf"\b{re.escape(n)}\b", reply, re.IGNORECASE)]
            if named or STATUS_DISCLOSURE.search(reply):
                v.append(f"reply names another patient or confirms patient status ({named or 'status'}) to an unverified "
                         "sender; neutral decline used")
                reply = FALLBACK_REPLIES["decline"][lang]
                actions -= {"answer_directly", "book_appointment", "offer_appointment", "offer_alternatives", "acknowledge"}
                actions.add("decline_disclosure")

        # 7. Always leave a reply and a human owner.
        if not reply and actions != {"no_action"}:
            reply = FALLBACK_REPLIES["ack"][lang]
            v.append("no reply drafted; acknowledgment used")
            routed = set(queues) | {r["queue"] for r in extra}
            if not routed and not (actions & set(TOOL_ACTIONS.values())):
                extra.append({"queue": "front_desk", "priority": urgency, "summary": "Agent produced no reply; please review."})
                actions.add("route_to_front_desk")

    # 8. Conversational actions mean exactly what their names say (see README, "Action vocabulary").
    booked = any(c["name"] in ("book_appointment", "reschedule_appointment") for c in ok_calls)
    if "needs_visit" in decisions:
        actions.discard("offer_alternatives")  # offering a visit because the policy requires one is an offer
    elif booked:
        actions.discard("offer_appointment")  # it was booked, not offered
    if not set(intents) & {"admin", "new_patient"}:
        actions.discard("answer_directly")  # only questions answerable from public clinic information
    if actions - {"acknowledge", "no_action"}:
        actions.discard("acknowledge")  # acknowledge is what a reply does when nothing else was done

    if "no_action" in actions and len(actions) > 1:
        actions.discard("no_action")

    routed_to = list(dict.fromkeys(queues + [r["queue"] for r in extra]))
    tool_calls = [c["name"] for c in trace] + ["route_to_queue"] * len(extra)
    result = AgentResult(id=message_id, patient_id=patient_id, intents=list(dict.fromkeys(intents)) or ["other"],
                         urgency=urgency, actions=_ordered(actions), routed_to=routed_to, tool_calls=tool_calls,
                         reply_draft=reply)
    return GuardOutcome(result, v, extra)
