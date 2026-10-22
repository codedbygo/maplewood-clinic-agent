"""Run the sample N times and count messages whose outcome changes between runs.

python -m eval.stability --runs 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from agent.cli import run_file

ROOT = Path(__file__).resolve().parent.parent


def outcome(r: dict) -> tuple:
    return (r["urgency"], tuple(sorted(r["actions"])), r["patient_id"], tuple(sorted(r["routed_to"])))


def compare(runs: list[list[dict]]) -> dict:
    by_run = [{r["id"]: r for r in run} for run in runs]
    ids = sorted(by_run[0])
    changed = {}
    for mid in ids:
        outs = [outcome(run[mid]) if mid in run else None for run in by_run]
        if len(set(outs)) > 1:
            changed[mid] = [{"missing": True} if o is None else
                            {"urgency": o[0], "actions": list(o[1]), "patient_id": o[2], "routed_to": list(o[3])} for o in outs]
    emergencies = {mid for run in by_run for mid, r in run.items() if "escalate_emergency" in r["actions"]}
    return {"runs": len(runs), "messages": len(ids), "changed": len(changed), "changed_ids": sorted(changed),
            "details": changed, "emergency_flips": sorted(mid for mid in emergencies if mid in changed)}


def build_report(runs: list[list[dict]], metas: list[dict]) -> dict:
    """Stability plus provenance: which model and runs it measured, so a stale file is never mistaken for current."""
    report = compare(runs)
    report.update(model=metas[0].get("model") if metas else None, provider=metas[0].get("provider") if metas else None,
                  run_ids=[m.get("run_id") for m in metas], complete=all(not m.get("stopped") for m in metas))
    return report


async def main_async(n: int, messages: Path, model: str | None) -> dict:
    runs, metas = [], []
    for i in range(n):
        out = ROOT / "results" / f"stability_run{i + 1}.json"
        r = await run_file(messages, out, model, quiet=True)
        runs.append(r["results"])
        metas.append(r["meta"])
        print(f"run {i + 1}/{n} done: {r['run_dir'].name}")
    report = build_report(runs, metas)
    (ROOT / "results" / "stability.json").write_text(json.dumps(report, indent=2))
    print(f"{report['changed']}/{report['messages']} messages changed outcome across {n} runs: {report['changed_ids']}")
    print(f"emergency decisions that flipped: {report['emergency_flips'] or 'none'}")
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--messages", default="data/messages_sample.json")
    p.add_argument("--model")
    a = p.parse_args()
    asyncio.run(main_async(a.runs, Path(a.messages), a.model))


if __name__ == "__main__":
    main()
