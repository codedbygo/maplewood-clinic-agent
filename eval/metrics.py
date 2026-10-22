"""Scores agent results against labels. Pure functions; harness.py does the I/O."""

from __future__ import annotations

from collections import defaultdict

ACTION_QUEUES = {
    "escalate_emergency": {"clinician_urgent"},
    "route_to_clinician": {"clinician_urgent", "clinician_routine"},
    "route_to_provider": {"provider_refills"},
    "prepare_refill_for_approval": {"provider_refills"},
    "route_to_billing": {"billing"},
    "route_to_front_desk": {"front_desk"},
}


def is_label_emergency(label: dict) -> bool:
    return "emergency" in label["accepted_urgency"] and "escalate_emergency" in label["expected_actions"]


def is_pred_emergency(result: dict) -> bool:
    return "escalate_emergency" in result["actions"]


def expected_queue_slots(actions: list[str]) -> list[set[str]]:
    slots: list[set[str]] = []
    for a in actions:
        q = ACTION_QUEUES.get(a)
        if q and q not in slots:
            slots.append(set(q))
    return slots


def routing_ok(routed: list[str], expected_actions: list[str]) -> bool:
    slots = expected_queue_slots(expected_actions)
    got = set(routed)
    allowed = set().union(*slots) if slots else set()
    return all(got & s for s in slots) and got <= allowed


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else (1.0 if not fn else 0.0)
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f, "tp": tp, "fp": fp, "fn": fn}


def _set_f1(pred: set, gold: set) -> float:
    if not pred and not gold:
        return 1.0
    tp = len(pred & gold)
    if not tp:
        return 0.0
    p, r = tp / len(pred), tp / len(gold)
    return 2 * p * r / (p + r)


def score(results: list[dict], labels: list[dict]) -> dict:
    by_id = {r["id"]: r for r in results}
    labels = [label for label in labels if label["id"] in by_id]
    n = len(labels)
    per_msg = []
    tp = fp = fn = 0
    action_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # tp, fp, fn
    emerg_tp, emerg_missed, over = 0, [], []
    for label in labels:
        r = by_id[label["id"]]
        pred, gold = set(r["actions"]), set(label["expected_actions"])
        for a in pred | gold:
            c = action_counts[a]
            c[0] += a in pred and a in gold
            c[1] += a in pred and a not in gold
            c[2] += a in gold and a not in pred
        tp += len(pred & gold)
        fp += len(pred - gold)
        fn += len(gold - pred)
        if is_label_emergency(label):
            if is_pred_emergency(r):
                emerg_tp += 1
            else:
                emerg_missed.append(label["id"])
        elif is_pred_emergency(r):
            over.append(label["id"])
        per_msg.append(
            {
                "id": label["id"],
                "urgency_ok": r["urgency"] in label["accepted_urgency"],
                "actions_exact": pred == gold,
                "intent_f1": _set_f1(set(r["intents"]), set(label["intents"])),
                "patient_ok": r["patient_id"] == label["patient_id"],
                "routing_ok": routing_ok(r["routed_to"], label["expected_actions"]),
                "missing_actions": sorted(gold - pred),
                "extra_actions": sorted(pred - gold),
            }
        )
    n_emerg = emerg_tp + len(emerg_missed)
    per_action = {a: _prf(*c) for a, c in sorted(action_counts.items())}
    gold_actions = [a for a, c in action_counts.items() if c[0] + c[2] > 0]
    mean = lambda key: sum(m[key] for m in per_msg) / n if n else 0.0  # noqa: E731
    return {
        "n": n,
        "urgency_accuracy": mean("urgency_ok"),
        "emergency": {
            "n_labelled": n_emerg,
            "recall": emerg_tp / n_emerg if n_emerg else 1.0,
            "precision": emerg_tp / (emerg_tp + len(over)) if emerg_tp + len(over) else 1.0,
            "missed": emerg_missed,
            "over_escalated": over,
        },
        "actions": {
            "exact_match": mean("actions_exact"),
            "micro": _prf(tp, fp, fn),
            "macro_f1": sum(per_action[a]["f1"] for a in gold_actions) / len(gold_actions) if gold_actions else 0.0,
            "per_action": per_action,
        },
        "intent_f1": mean("intent_f1"),
        "patient_id_accuracy": mean("patient_ok"),
        "routing_accuracy": mean("routing_ok"),
        "per_message": per_msg,
    }
