import pytest

from agent.safety import EMERGENCY_TEMPLATE, detect_language, prescreen

EMERGENCIES = [
    # sample-shaped clinical content, reworded
    "Woke up with crushing chest pain going into my left arm, sweaty and dizzy",
    "Mom fell and hit her head, now she seems confused",
    "My inhaler isn't helping, I'm wheezing and can't finish sentences",
    "Blood sugar was 45 and I'm shaky and sweaty",
    "On warfarin, gums bleeding a lot and I have dark stools",
    "I want to end my life",
    # unseen phrasings
    "my face is drooping on one side and my words are slurred",
    "my throat is swelling after eating peanuts",
    "I took all my pills an hour ago",
    "tengo dolor de pecho muy fuerte",
    "no puedo respirar bien",
    "my chest feels tight and I can't catch my breath, not dying lol",  # Review Focus 1
    "I've been thinking about killing myself",
    "honestly everyone would be better off if I was dead",
    "I don't want to be here anymore",
    "he had a seizure and won't wake up",
    "my lips are turning blue",
    "sugar is 38, feel confused",
    "vomiting blood this morning",
    "worst headache of my life came on suddenly",
    "she passed out and is unresponsive",
    "I cut myself again last night",
    "heavy pressure in my chest",
    "sudden weakness in my left arm and leg",
    "quiero morir",
]

URGENT = [
    "I've been feeling really low lately and some days I don't see the point of anything",
    "feeling hopeless",
    "my 3 year old has a fever of 101 and a cough",
    "I hit my head yesterday, it hurts",
    "sugar has been 62 this morning",
    "had an allergic reaction to the new pill, itchy rash",
]

NONE = [
    "I'm dying to get in before my trip lol, any chance of a physical this week?",
    "my bill is killing me, what's the balance?",
    "What are your clinic hours?",
    "I think I have a UTI, burning when I pee since yesterday, no fever.",
    "Please refill my metformin.",
    "Thanks so much for the help yesterday!",
    "Can you explain what high TSH means?",
    "you nearly gave me a heart attack with that bill",
    "Special offer on medical billing services this month only.",
]


@pytest.mark.parametrize("text", EMERGENCIES)
def test_emergency_tier(text):
    r = prescreen(text)
    assert r["tier"] == "emergency", r


@pytest.mark.parametrize("text", URGENT)
def test_urgent_clinical_tier(text):
    r = prescreen(text)
    assert r["tier"] == "urgent_clinical", r


@pytest.mark.parametrize("text", NONE)
def test_no_flag(text):
    r = prescreen(text)
    assert r["tier"] == "none", r


def test_matches_name_the_rules():
    r = prescreen("Woke up with crushing chest pain going into my left arm")
    assert "chest_pain" in r["matches"]


def test_idiom_does_not_mask_a_real_red_flag():
    assert prescreen("dying to see you lol but also I can't breathe")["tier"] == "emergency"


def test_negation_never_suppresses_emergency_rules():
    # A false alarm is cheap; a miss is not.
    assert prescreen("no chest pain but my left arm is numb and my chest feels heavy")["tier"] == "emergency"


def test_language_detection():
    assert detect_language("Hola, necesito una cita para mi chequeo anual") == "es"
    assert detect_language("Necesito más metformina por favor.") == "es"
    assert detect_language("Please refill my metformin.") == "en"


def test_spanish_emergency_uses_spanish_template():
    r = prescreen("tengo dolor de pecho y no puedo respirar")
    assert r["language"] == "es"
    assert "911" in EMERGENCY_TEMPLATE["es"]


def test_template_only_advises_911_or_ed_and_says_clinic_alerted():
    t = EMERGENCY_TEMPLATE["en"].lower()
    assert "911" in t and "emergency department" in t and "alerted" in t
