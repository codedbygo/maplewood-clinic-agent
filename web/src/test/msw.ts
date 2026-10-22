import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import {
  fixtureClinic,
  fixtureEval,
  fixtureInbox,
  fixtureResult,
  fixtureScreen,
  fixtureState,
  fixtureTriage,
} from "./fixtures";

/**
 * Mock Service Worker for unit tests: one default handler per route the app
 * calls. setup.ts starts it with onUnhandledRequest "error", so a wrong path
 * fails the test. A test that needs another answer calls server.use(...).
 */

export function sseBody(events: unknown[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const e of events) controller.enqueue(enc.encode(`data: ${JSON.stringify(e)}\n\n`));
      controller.close();
    },
  });
}

export const liveRunEvents = [
  {
    type: "message",
    data: {
      id: "LIVE-1",
      channel: "sms",
      from_name: "Robert Chen",
      from_contact: "555-0102",
      body: "refill please",
    },
  },
  { type: "stage", stage: "prescreen", data: fixtureScreen("none") },
  {
    type: "tool",
    name: "verify_sender",
    input: {},
    ok: true,
    output: { status: "verified_patient", reason: "Contact on file." },
  },
  { type: "stage", stage: "triage", data: fixtureTriage() },
  {
    type: "tool",
    name: "check_refill_eligibility",
    input: { medication_query: "lisinopril" },
    ok: true,
    output: { decision: "prepare" },
  },
  { type: "stage", stage: "path", data: { path: "normal", error: null } },
  { type: "guard", data: { violations: [], extra_routes: [] } },
  { type: "result", data: fixtureResult({ id: "LIVE-1" }), latency_s: 4.2, llm_calls: [] },
];

export const handlers = [
  http.get("*/api/health", () =>
    HttpResponse.json({
      ok: true,
      model: "claude-sonnet-5-5",
      effort: "medium",
      llm_configured: true,
    }),
  ),
  http.get("*/api/datasets", () =>
    HttpResponse.json([
      { id: "sample", label: "Sample messages", messages: 40, has_results: true, has_eval: true },
      {
        id: "holdout",
        label: "Held-out messages",
        messages: 13,
        has_results: false,
        has_eval: false,
      },
    ]),
  ),
  http.get("*/api/datasets/:name/inbox", ({ params }) =>
    HttpResponse.json(
      params.name === "holdout" ? { dataset: "holdout", run: null, items: [] } : fixtureInbox(),
    ),
  ),
  http.get("*/api/datasets/:name/eval", ({ params }) =>
    params.name === "sample"
      ? HttpResponse.json(fixtureEval())
      : HttpResponse.json({ error: "none" }, { status: 404 }),
  ),
  http.get("*/api/datasets/:name/state", () => HttpResponse.json(fixtureState())),
  http.get("*/api/clinic", () => HttpResponse.json(fixtureClinic())),
  http.get("*/api/stability", () => HttpResponse.json({ error: "none" }, { status: 404 })),
  http.get("*/api/live/state", () => HttpResponse.json(fixtureState())),
  http.post("*/api/live/reset", () => HttpResponse.json({ ok: true })),
  http.post(
    "*/api/live/process",
    () =>
      new HttpResponse(sseBody(liveRunEvents), {
        headers: { "Content-Type": "text/event-stream" },
      }),
  ),
];

export const server = setupServer(...handlers);
