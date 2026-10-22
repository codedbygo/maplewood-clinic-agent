"""Render the evaluation as Markdown and JSON."""

from __future__ import annotations

import json
from pathlib import Path

from agent.safety import EMERGENCY_TEMPLATE


def _p(x: float) -> str:
    return f"{100 * x:.1f}%"


def _trace_line(call: dict) -> str:
    inp = {k: v for k, v in call.get("input", {}).items() if k != "verification_token" and v not in (None, "")}
    if call["name"] == "draft_reply":
        inp = {"language": inp.get("language")}
    out = call.get("output", {})
    detail = out.get("decision") or ("ok" if call.get("ok") else "refused")
    if out.get("violations"):
        detail += f" {out['violations']}"
    args = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)[:60]}" for k, v in inp.items())
    return f"`{call['name']}({args})` -> {detail}"


def write_report(ev: dict, out_prefix: Path) -> str:
    s, m = ev["scores"], ev["meta"]
    em = s["emergency"]
    lines = [
        f"# Evaluation report: {Path(m['messages']).name}",
        "",
        f"Run `{m['run_id']}`, model `{m['model']}` (effort `{m['effort']}`), {m['n']} messages, wall time {m['wall_s']}s. "
        f"Labels: `{ev['labels']}`. Regenerate with `make eval`.",
        "",
        "LLM calls served by: " + (", ".join(f"`{k}` ({v})" for k, v in sorted(ev.get("models_served", {}).items(), key=lambda kv: -kv[1])) or "none")
        + ("" if not m.get("stopped") else f". **Run incomplete**: stopped at {m['stopped']['at']} ({m['stopped']['reason']})") + ".",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Emergency recall | **{_p(em['recall'])}** ({em['n_labelled'] - len(em['missed'])}/{em['n_labelled']}) |",
        f"| Emergency precision | {_p(em['precision'])} (over-escalated: {', '.join(em['over_escalated']) or 'none'}) |",
        f"| must_not violations | **{len(ev['must_not_violations'])}** |",
        f"| Global safety check findings | {len(ev['global_safety'])} |",
        f"| Urgency accuracy | {_p(s['urgency_accuracy'])} |",
        f"| Actions: exact set match | {_p(s['actions']['exact_match'])} |",
        f"| Actions: micro P / R / F1 | {_p(s['actions']['micro']['precision'])} / {_p(s['actions']['micro']['recall'])} / {_p(s['actions']['micro']['f1'])} |",
        f"| Actions: macro F1 | {_p(s['actions']['macro_f1'])} |",
        f"| Intent set F1 | {_p(s['intent_f1'])} |",
        f"| patient_id accuracy | {_p(s['patient_id_accuracy'])} |",
        f"| Routing accuracy | {_p(s['routing_accuracy'])} |",
        f"| Cost, full run | ${ev['cost']['total_usd']:.3f} (${ev['cost']['mean_usd_per_message']:.4f}/message) |",
        f"| Latency p50 / p95 | {ev['latency']['p50_s']:.1f}s / {ev['latency']['p95_s']:.1f}s |",
        f"| Paths | {', '.join(f'{k}: {v}' for k, v in sorted(ev['paths'].items(), key=lambda kv: str(kv[0])))} |",
        "",
        "## Emergencies",
        "",
    ]
    if em["missed"]:
        lines.append("**Missed emergencies:**")
        lines += [f"- {mid}: got {ev['_results'][mid]['actions']} / {ev['_results'][mid]['urgency']}" for mid in em["missed"]]
    else:
        lines.append("Missed emergencies: **none**.")
    lines += ["", "| id | caught | caught by | reply is template |", "|---|---|---|---|"]
    for mid, l in ev["_labels"].items():
        if "escalate_emergency" in l["expected_actions"] and mid in ev["_results"]:
            r, log = ev["_results"][mid], ev["_logs"].get(mid, {})
            by = "pre-screen" if log.get("screen", {}).get("tier") == "emergency" else ("LLM triage" if log.get("path") == "emergency" else "-")
            lines.append(f"| {mid} | {'yes' if 'escalate_emergency' in r['actions'] else '**NO**'} | {by} | "
                         f"{'yes' if r['reply_draft'] in EMERGENCY_TEMPLATE.values() else '**no**'} |")
    lines += ["", "## must_not violations", ""]
    if ev["must_not_violations"]:
        lines += ["| id | tag | evidence |", "|---|---|---|"] + [f"| {v['id']} | {v['tag']} | {v['evidence']} |" for v in ev["must_not_violations"]]
    else:
        lines.append("None. Every `must_not` tag in the labels was checked against the reply, the tool trace and the final store state.")
    lines += ["", "## Global safety checks (every message)", ""]
    if ev["global_safety"]:
        lines += ["| id | check | evidence |", "|---|---|---|"] + [f"| {g['id']} | {g['check']} | {g['evidence']} |" for g in ev["global_safety"]]
    else:
        lines.append("None: no invalid bookings, approvals, non-template emergency replies, clinical-advice keywords or PHI to unverified senders.")
    lines += ["", "## Per-action results", "", "| action | precision | recall | support |", "|---|---|---|---|"]
    for a, v in s["actions"]["per_action"].items():
        lines.append(f"| {a} | {_p(v['precision'])} | {_p(v['recall'])} | {v['tp'] + v['fn']} |")
    if ev["guard_interventions"]:
        lines += ["", "## Post-guard interventions", "", "The deterministic guard changed these results before they were emitted:", ""]
        lines += [f"- {mid}: {'; '.join(v)}" for mid, v in sorted(ev["guard_interventions"].items())]
    t = ev["cost"]["tokens"]
    lines += ["", "## Cost and latency", "",
              f"Tokens: {t['input_tokens']:,} input, {t['output_tokens']:,} output, {t['cache_read_input_tokens']:,} cache read, "
              f"{t['cache_creation_input_tokens']:,} cache write. Total ${ev['cost']['total_usd']:.3f}; "
              f"p50 {ev['latency']['p50_s']:.1f}s, p95 {ev['latency']['p95_s']:.1f}s, max {ev['latency']['max_s']:.1f}s per message."]

    lines += ["", "## Every wrong case", "",
              "A case is listed if any of urgency, the exact action set, patient_id, routing or intents differs from the label."]
    wrong = [pm for pm in s["per_message"] if not (pm["urgency_ok"] and pm["actions_exact"] and pm["patient_ok"] and pm["routing_ok"] and pm["intent_f1"] == 1.0)]
    for pm in wrong:
        mid = pm["id"]
        r, l, log = ev["_results"][mid], ev["_labels"][mid], ev["_logs"].get(mid, {})
        lines += [f"### {mid}", "",
                  f"- Message ({log.get('from_name')}): {log.get('body', '')!r}; path `{log.get('path')}`, "
                  f"pre-screen `{log.get('screen', {}).get('tier')}`, sender `{log.get('verification', {}).get('status')}`",
                  f"- Urgency: expected {l['accepted_urgency']}, got `{r['urgency']}`" + ("" if pm["urgency_ok"] else " **wrong**"),
                  f"- Actions: expected {sorted(l['expected_actions'])}, got {r['actions']}"
                  + (f" (missing {pm['missing_actions']}, extra {pm['extra_actions']})" if not pm["actions_exact"] else ""),
                  f"- patient_id: expected `{l['patient_id']}`, got `{r['patient_id']}`" + ("" if pm["patient_ok"] else " **wrong**"),
                  f"- Routed: {r['routed_to']}" + ("" if pm["routing_ok"] else " **routing wrong**"),
                  f"- Intents: expected {l['intents']}, got {r['intents']}",
                  f"- Root cause: {ev['root_causes'].get(mid, '_not yet analysed_')}",
                  "- Trace:"]
        lines += [f"  {i + 1}. {_trace_line(c)}" for i, c in enumerate(log.get("trace", []))]
        if log.get("guard_violations"):
            lines.append(f"- Guard: {'; '.join(log['guard_violations'])}")
        lines.append(f"- Reply: {r['reply_draft'][:300]!r}")
        lines.append("")
    if not wrong:
        lines.append("None.")

    md = "\n".join(lines) + "\n"
    out_prefix = Path(out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".md").write_text(md)
    public = {k: v for k, v in ev.items() if not k.startswith("_")}
    out_prefix.with_suffix(".json").write_text(json.dumps(public, indent=2, default=str))
    return md
