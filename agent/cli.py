"""CLI: process one message (live demo) or run a whole message file.

python -m agent.cli process --text "..." --from "Jane Doe" --contact 555-0101 --channel sms
python -m agent.cli run --messages data/messages_sample.json --out results/results_sample.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from agent.llm import LLM, LLMQuotaError, cost_usd
from agent.runner import ROOT, open_clinic, process_message

console = Console()


def _show(result, log) -> None:
    t = Table(title=f"{result.id}  ({log['path']} path, {log['latency_s']}s)", show_header=False)
    for k, v in result.model_dump().items():
        t.add_row(k, json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v)
    if log["guard_violations"]:
        t.add_row("[yellow]guard[/yellow]", "; ".join(log["guard_violations"]))
    console.print(t)


async def _process(args) -> None:
    msg = {
        "id": args.id,
        "received_at": args.received_at,
        "channel": args.channel,
        "from_name": args.sender,
        "from_contact": args.contact,
        "body": args.text,
    }
    if args.dob:
        msg["stated_dob"] = args.dob
    llm = LLM(model=args.model)
    async with open_clinic() as clinic:
        await clinic.reset()
        result, log = await process_message(msg, clinic, llm)
    _show(result, log)
    if args.json:
        console.print_json(json.dumps({"result": result.model_dump(), "trace": log["trace"]}, default=str))


async def run_file(messages_path: Path, out_path: Path, model: str | None = None, quiet: bool = False) -> dict:
    messages = sorted(json.loads(Path(messages_path).read_text()), key=lambda m: m.get("received_at", ""))
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "results" / "runs" / f"{run_id}_{Path(messages_path).stem}"
    run_dir.mkdir(parents=True, exist_ok=True)
    llm = LLM(model=model)
    results: list[dict] = []
    started, stopped = time.monotonic(), None
    async with open_clinic() as clinic:
        await clinic.reset()
        for msg in messages:
            try:
                result, log = await process_message(msg, clinic, llm, fail_on_quota=True)
            except LLMQuotaError as e:
                stopped = {"reason": str(e), "at": msg["id"], "not_processed": [m["id"] for m in messages[len(results) :]]}
                console.print(f"[bold red]Stopped at {msg['id']}: {e}[/bold red]")
                break
            results.append(result.model_dump())
            (run_dir / f"{msg['id']}.json").write_text(json.dumps(log, indent=2, default=str, ensure_ascii=False))
            if not quiet:
                cost = sum(cost_usd(c["model"], c) for c in log["llm_calls"])
                console.print(
                    f"{msg['id']:>6} {log['path']:<9} {result.urgency:<9} {','.join(result.actions):<70} "
                    f"{log['latency_s']:>5}s ${cost:.4f}"
                    + (f" [yellow]guard:{len(log['guard_violations'])}[/yellow]" if log["guard_violations"] else "")
                )
        state = await clinic.export_state()
    (run_dir / "final_state.json").write_text(json.dumps(state, indent=2, default=str))
    meta = {
        "run_id": run_id,
        "provider": getattr(llm, "provider", "anthropic"),
        "model": llm.model,
        "fallbacks": getattr(llm, "fallbacks", []),
        "effort": llm.effort,
        "messages": str(messages_path),
        "n": len(results),
        "wall_s": round(time.monotonic() - started, 1),
        "stopped": stopped,
        "llm_calls": llm.calls,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    (out_path.parent / f"{out_path.stem}.run").write_text(str(run_dir.relative_to(ROOT)))
    total = sum(cost_usd(c["model"], c) for c in llm.calls)
    if not quiet:
        console.print(
            f"[bold]{len(results)} messages, {meta['wall_s']}s, ${total:.3f} ({llm.model}). "
            f"Results: {out_path}  Logs: {run_dir.relative_to(ROOT)}[/bold]"
        )
    return {"results": results, "run_dir": run_dir, "meta": meta}


def main() -> None:
    p = argparse.ArgumentParser(prog="agent.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("process", help="process one message")
    pr.add_argument("--text", required=True)
    pr.add_argument("--from", dest="sender", required=True)
    pr.add_argument("--contact", default="")
    pr.add_argument("--channel", default="sms", choices=["sms", "portal", "email"])
    pr.add_argument("--dob", help="stated date of birth, YYYY-MM-DD")
    pr.add_argument("--id", default="LIVE-1")
    pr.add_argument("--received-at", default="2026-11-09T09:00:00-06:00")
    pr.add_argument("--model")
    pr.add_argument("--json", action="store_true", help="also print the result and tool trace as JSON")
    rn = sub.add_parser("run", help="process a message file")
    rn.add_argument("--messages", default="data/messages_sample.json")
    rn.add_argument("--out", default="results/results_sample.json")
    rn.add_argument("--model")
    args = p.parse_args()
    if args.cmd == "process":
        asyncio.run(_process(args))
    else:
        out = asyncio.run(run_file(Path(args.messages), Path(args.out), args.model))
        if out["meta"]["stopped"]:
            console.print(
                f"[red]Incomplete run: {len(out['meta']['stopped']['not_processed'])} messages not processed. "
                "Results so far are saved; rerun when the quota resets.[/red]"
            )
            raise SystemExit(2)


if __name__ == "__main__":
    main()
