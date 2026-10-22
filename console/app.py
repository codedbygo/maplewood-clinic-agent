from __future__ import annotations

import asyncio
import itertools
import json
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from agent.llm import LLM
from agent.runner import ROOT, open_clinic, process_message

DATASETS = {
    "sample": {
        "label": "Sample messages",
        "messages": "data/messages_sample.json",
        "labels": "data/labels_sample.json",
        "results": "results_sample.json",
        "eval": "eval_report.json",
    },
    "holdout": {
        "label": "Held-out messages",
        "messages": "eval/holdout_messages.json",
        "labels": "eval/holdout_labels.json",
        "results": "results_holdout.json",
        "eval": "eval_report_holdout.json",
    },
}
LOG_FIELDS = (
    "path",
    "error",
    "screen",
    "triage",
    "verification",
    "trace",
    "final_answer",
    "guard_violations",
    "extra_routes",
    "latency_s",
    "llm_calls",
)


class LiveMessage(BaseModel):
    from_name: str = Field(min_length=1, max_length=120)
    from_contact: str = Field(min_length=1, max_length=120)
    channel: Literal["sms", "portal", "email"]
    body: str = Field(min_length=1, max_length=4000)
    stated_dob: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    received_at: datetime | None = None  # parsed, so a malformed time is a 422, not a stale clock


async def live_events(msg: dict, clinic, llm, lock: asyncio.Lock):
    """Run one message and yield its events as server-sent events, one message at a time (shared MCP session)."""
    queue: asyncio.Queue = asyncio.Queue()
    async with lock:
        yield f"data: {json.dumps({'type': 'message', 'data': msg}, ensure_ascii=False)}\n\n"
        task = asyncio.create_task(process_message(msg, clinic, llm, emit=queue.put_nowait))
        try:
            while not (task.done() and queue.empty()):
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.2)
                except TimeoutError:
                    continue
                yield f"data: {json.dumps(event, default=str, ensure_ascii=False)}\n\n"
            if task.exception() is not None:
                yield f"data: {json.dumps({'type': 'error', 'error': repr(task.exception())})}\n\n"
        finally:
            # A client disconnect closes this generator: stop the run before releasing the lock, or its
            # tool calls would land in the next message's trace on the shared session.
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


def _json(obj, status: int = 200) -> Response:
    return Response(json.dumps(obj, default=str, ensure_ascii=False), status_code=status, media_type="application/json")


def _read(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def create_app(results_dir: Path = ROOT / "results", static_dir: Path | None = ROOT / "web" / "dist", llm_factory=LLM) -> Starlette:
    results_dir = Path(results_dir)
    counter = itertools.count(1)
    lock = asyncio.Lock()
    clinic_json = json.loads((ROOT / "data" / "clinic.json").read_text())
    patients = json.loads((ROOT / "data" / "patients.json").read_text())

    def run_dir(ds: dict) -> Path | None:
        pointer = results_dir / Path(ds["results"]).with_suffix(".run").name
        if not pointer.exists():
            return None
        p = Path(pointer.read_text().strip())
        return p if p.is_absolute() else ROOT / p

    def dataset(name: str) -> dict | None:
        return DATASETS.get(name)

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            app.state.clinic = await stack.enter_async_context(open_clinic())
            await app.state.clinic.reset()
            app.state.llm = llm_factory()
            yield

    async def health(request: Request):
        llm = request.app.state.llm
        return _json(
            {
                "ok": True,
                "provider": getattr(llm, "provider", None),
                "model": getattr(llm, "model", None),
                "effort": getattr(llm, "effort", None),
                "llm_configured": bool(getattr(llm, "configured", False)),
            }
        )

    async def datasets(request: Request):
        out = []
        for name, ds in DATASETS.items():
            out.append(
                {
                    "id": name,
                    "label": ds["label"],
                    "messages": len(json.loads((ROOT / ds["messages"]).read_text())),
                    "has_results": (results_dir / ds["results"]).exists(),
                    "has_eval": (results_dir / ds["eval"]).exists(),
                }
            )
        return _json(out)

    async def inbox(request: Request):
        ds = dataset(request.path_params["name"])
        if ds is None:
            return _json({"error": "unknown dataset"}, 404)
        messages = json.loads((ROOT / ds["messages"]).read_text())
        labels = {label["id"]: label for label in json.loads((ROOT / ds["labels"]).read_text())}
        results = {r["id"]: r for r in (_read(results_dir / ds["results"]) or [])}
        rd = run_dir(ds) if results else None
        report = _read(results_dir / ds["eval"]) or {}
        per_msg = {pm["id"]: pm for pm in report.get("scores", {}).get("per_message", [])}
        items = []
        for m in sorted(messages, key=lambda m: m.get("received_at", "")):
            log = _read(rd / f"{m['id']}.json") if rd else None
            items.append(
                {
                    "message": m,
                    "label": labels.get(m["id"]),
                    "result": results.get(m["id"]),
                    "log": {k: log.get(k) for k in LOG_FIELDS} if log else None,
                    "score": per_msg.get(m["id"]),
                    "root_cause": report.get("root_causes", {}).get(m["id"]),
                }
            )
        return _json({"dataset": request.path_params["name"], "run": _read(rd / "meta.json") if rd else None, "items": items})

    async def eval_report(request: Request):
        ds = dataset(request.path_params["name"])
        report = _read(results_dir / ds["eval"]) if ds else None
        return _json(report) if report is not None else _json({"error": "no evaluation yet; run make eval"}, 404)

    async def run_state(request: Request):
        ds = dataset(request.path_params["name"])
        rd = run_dir(ds) if ds else None
        state = _read(rd / "final_state.json") if rd else None
        return _json(state) if state is not None else _json({"error": "no run yet"}, 404)

    async def clinic(request: Request):
        return _json(
            {
                "clinic": clinic_json,
                "patients": [{"id": p["id"], "name": p["name"], "primary_provider": p["primary_provider"]} for p in patients],
            }
        )

    async def stability(request: Request):
        rep = _read(results_dir / "stability.json")
        return _json(rep) if rep is not None else _json({"error": "no stability run yet; run make stability"}, 404)

    async def live_state(request: Request):
        state = await request.app.state.clinic.export_state()
        return _json({k: state.get(k, []) for k in ("appointments", "refill_requests", "routes", "flags", "drafts")})

    async def live_reset(request: Request):
        async with lock:
            await request.app.state.clinic.reset()
        return _json({"ok": True})

    async def live_process(request: Request):
        app = request.app
        try:
            body = LiveMessage.model_validate(await request.json())
        except (ValidationError, ValueError) as e:
            detail = e.errors(include_url=False) if isinstance(e, ValidationError) else str(e)
            return _json({"error": "invalid message", "detail": detail}, 422)
        msg = {
            "id": f"LIVE-{next(counter)}",
            "channel": body.channel,
            "from_name": body.from_name,
            "from_contact": body.from_contact,
            "body": body.body.strip(),
            "received_at": body.received_at.isoformat() if body.received_at else f"{clinic_json['today']}T09:00:00-06:00",
        }
        if body.stated_dob:
            msg["stated_dob"] = body.stated_dob
        return StreamingResponse(
            live_events(msg, app.state.clinic, app.state.llm, lock), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    async def api_not_found(request: Request):
        return _json({"error": "not found"}, 404)

    async def spa(request: Request):
        if static_dir is None or not (Path(static_dir) / "index.html").exists():
            return JSONResponse({"error": "frontend not built; run make ui"}, 404)
        root = Path(static_dir).resolve()
        target = (root / request.path_params.get("path", "")).resolve()
        if target.is_file() and root in target.parents and target.name != "index.html":
            # Vite names built assets by content hash, so they can be cached forever.
            immutable = "assets" in target.relative_to(root).parts
            return FileResponse(target, headers={"Cache-Control": "public, max-age=31536000, immutable" if immutable else "no-cache"})
        # index.html must be revalidated every time, or a new build never reaches the browser.
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})

    routes = [
        Route("/api/health", health),
        Route("/api/datasets", datasets),
        Route("/api/datasets/{name}/inbox", inbox),
        Route("/api/datasets/{name}/eval", eval_report),
        Route("/api/datasets/{name}/state", run_state),
        Route("/api/clinic", clinic),
        Route("/api/stability", stability),
        Route("/api/live/state", live_state),
        Route("/api/live/reset", live_reset, methods=["POST"]),
        Route("/api/live/process", live_process, methods=["POST"]),
        Route("/api/{rest:path}", api_not_found),
        Route("/{path:path}", spa),
    ]
    return Starlette(routes=routes, lifespan=lifespan)


app = create_app()
