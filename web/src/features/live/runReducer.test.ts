import { describe, expect, it } from "vitest";

import { fixtureResult, fixtureScreen, fixtureTriage } from "@/test/fixtures";

import { initialRun, runReducer } from "./runReducer";

describe("runReducer", () => {
  it("moves from running to done as events arrive", () => {
    let s = runReducer(initialRun, { kind: "start" });
    expect(s.status).toBe("running");
    s = runReducer(s, {
      kind: "event",
      event: { type: "stage", stage: "prescreen", data: fixtureScreen("none") },
    });
    s = runReducer(s, {
      kind: "event",
      event: {
        type: "tool",
        name: "verify_sender",
        input: {},
        ok: true,
        output: { status: "verified_patient" },
      },
    });
    s = runReducer(s, {
      kind: "event",
      event: { type: "stage", stage: "triage", data: fixtureTriage() },
    });
    s = runReducer(s, {
      kind: "event",
      event: { type: "stage", stage: "path", data: { path: "normal", error: null } },
    });
    s = runReducer(s, {
      kind: "event",
      event: { type: "guard", data: { violations: ["x"], extra_routes: [] } },
    });
    s = runReducer(s, {
      kind: "event",
      event: { type: "result", data: fixtureResult(), latency_s: 2.5, llm_calls: [] },
    });
    expect(s.status).toBe("done");
    expect(s.screen?.tier).toBe("none");
    expect(s.tools).toHaveLength(1);
    expect(s.triage?.urgency).toBe("routine");
    expect(s.path).toBe("normal");
    expect(s.guard).toEqual(["x"]);
    expect(s.result?.id).toBe("M001");
    expect(s.latency).toBe(2.5);
  });

  it("records a triage failure without failing the run", () => {
    const s = runReducer(runReducer(initialRun, { kind: "start" }), {
      kind: "event",
      event: { type: "stage", stage: "triage", data: null, error: "no key" },
    });
    expect(s.status).toBe("running");
    expect(s.triageError).toBe("no key");
  });

  it("ends in error on an error event or a failure", () => {
    const a = runReducer(initialRun, { kind: "event", event: { type: "error", error: "boom" } });
    expect(a).toMatchObject({ status: "error", error: "boom" });
    const b = runReducer(initialRun, { kind: "fail", error: "network" });
    expect(b).toMatchObject({ status: "error", error: "network" });
  });

  it("start clears the previous run", () => {
    const done = runReducer(initialRun, {
      kind: "event",
      event: { type: "result", data: fixtureResult(), latency_s: 1, llm_calls: [] },
    });
    expect(runReducer(done, { kind: "start" }).result).toBeUndefined();
  });

  it("keeps the assigned message", () => {
    const s = runReducer(initialRun, {
      kind: "event",
      event: {
        type: "message",
        data: { id: "LIVE-1", channel: "sms", from_name: "A", from_contact: "1", body: "hi" },
      },
    });
    expect(s.message?.id).toBe("LIVE-1");
  });
});
