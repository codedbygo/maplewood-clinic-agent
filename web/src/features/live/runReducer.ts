import type {
  AgentResult,
  InboxMessage,
  Screen,
  TraceCall,
  Triage,
} from "@/features/inbox/schemas";

import type { LiveEvent } from "./schemas";

/** The state of one streamed run. Client-only: it is built from the event stream, not cached server data. */
export interface RunState {
  status: "idle" | "running" | "done" | "error";
  message?: InboxMessage;
  screen?: Screen;
  triage?: Triage;
  triageError?: string;
  path?: string | null;
  tools: TraceCall[];
  guard?: string[];
  result?: AgentResult;
  latency?: number;
  error?: string;
}

export type RunAction =
  { kind: "start" } | { kind: "event"; event: LiveEvent } | { kind: "fail"; error: string };

export const initialRun: RunState = { status: "idle", tools: [] };

export function runReducer(state: RunState, action: RunAction): RunState {
  if (action.kind === "start") return { status: "running", tools: [] };
  if (action.kind === "fail") return { ...state, status: "error", error: action.error };
  const e = action.event;
  switch (e.type) {
    case "message":
      return { ...state, message: e.data };
    case "stage":
      if (e.stage === "prescreen") return { ...state, screen: e.data };
      if (e.stage === "triage")
        return e.data
          ? { ...state, triage: e.data }
          : { ...state, triageError: e.error ?? "Triage failed" };
      return { ...state, path: e.data.path };
    case "tool":
      return {
        ...state,
        tools: [...state.tools, { name: e.name, input: e.input, ok: e.ok, output: e.output }],
      };
    case "guard":
      return { ...state, guard: e.data.violations };
    case "result":
      return { ...state, status: "done", result: e.data, latency: e.latency_s };
    case "error":
      return { ...state, status: "error", error: e.error };
  }
}
