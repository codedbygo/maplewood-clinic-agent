"""Score a run: python -m eval.harness --results results/results_sample.json --labels data/labels_sample.json"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from agent.llm import cost_usd
from eval.metrics import score
from eval.must_not import check_must_not, global_safety_checks
from eval.report import write_report

ROOT = Path(__file__).resolve().parent.parent


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(q * (len(s) - 1))))
    return s[k]


def evaluate(results_path: Path, labels_path: Path, run_dir: Path | None = None) -> dict:
    results = json.loads(Path(results_path).read_text())
    labels = json.loads(Path(labels_path).read_text())
    if run_dir is None:
        pointer = Path(results_path).with_suffix(".run")
        run_dir = ROOT / pointer.read_text().strip()
    run_dir = Path(run_dir)
    logs = {p.stem: json.loads(p.read_text()) for p in run_dir.glob("*.json") if p.stem not in ("final_state", "meta")}
    state = json.loads((run_dir / "final_state.json").read_text())
    meta = json.loads((run_dir / "meta.json").read_text())

    s = score(results, labels)
    by_id = {r["id"]: r for r in results}
    violations = []
    for l in labels:
        r = by_id.get(l["id"])
        if r is None:
            continue
        for tag in l["must_not"]:
            ev = check_must_not(tag, r, logs.get(l["id"], {}), state, l)
            if ev:
                violations.append({"id": l["id"], "tag": tag, "evidence": ev})
    global_found = global_safety_checks(results, logs, state)

    per_msg_cost = {mid: sum(cost_usd(c["model"], c) for c in log.get("llm_calls", [])) for mid, log in logs.items()}
    served: dict[str, int] = {}
    for log in logs.values():
        for c in log.get("llm_calls", []):
            served[c["model"]] = served.get(c["model"], 0) + 1
    latencies = [log.get("latency_s", 0.0) for log in logs.values()]
    tokens = {k: sum(c.get(k, 0) for log in logs.values() for c in log.get("llm_calls", []))
              for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
    paths = {}
    for log in logs.values():
        paths[log.get("path")] = paths.get(log.get("path"), 0) + 1

    root_causes_path = ROOT / "eval" / "root_causes.json"
    root_causes = json.loads(root_causes_path.read_text()) if root_causes_path.exists() else {}
    return {
        "meta": {k: meta.get(k) for k in ("run_id", "provider", "model", "fallbacks", "effort", "messages", "n", "wall_s", "stopped")},
        "models_served": served,
        "labels": str(labels_path),
        "scores": s,
        "must_not_violations": violations,
        "global_safety": global_found,
        "cost": {"total_usd": sum(per_msg_cost.values()), "mean_usd_per_message": statistics.mean(per_msg_cost.values()) if per_msg_cost else 0.0,
                 "per_message_usd": per_msg_cost, "tokens": tokens},
        "latency": {"p50_s": _pct(latencies, 0.5), "p95_s": _pct(latencies, 0.95), "max_s": max(latencies, default=0.0)},
        "paths": paths,
        "guard_interventions": {mid: log.get("guard_violations", []) for mid, log in logs.items() if log.get("guard_violations")},
        "root_causes": root_causes,
        "_results": by_id,
        "_labels": {l["id"]: l for l in labels},
        "_logs": logs,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--results", default="results/results_sample.json")
    p.add_argument("--labels", default="data/labels_sample.json")
    p.add_argument("--run-dir")
    p.add_argument("--out", default="results/eval_report")
    a = p.parse_args()
    ev = evaluate(Path(a.results), Path(a.labels), Path(a.run_dir) if a.run_dir else None)
    md = write_report(ev, Path(a.out))
    print(md.split("## Every wrong case")[0])


if __name__ == "__main__":
    main()
