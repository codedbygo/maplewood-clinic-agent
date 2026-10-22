import { useQueryClient } from "@tanstack/react-query";
import { useReducer, useRef } from "react";

import { stateKeys } from "@/features/state/hooks";
import { ApiError } from "@/lib/api";
import { postEventStream } from "@/lib/sse";

import { initialRun, runReducer } from "./runReducer";
import { liveEventSchema, type ComposePayload } from "./schemas";

/** A result or error event, even one that fails validation, ends the run. */
function isTerminal(raw: unknown): boolean {
  return (
    typeof raw === "object" &&
    raw !== null &&
    "type" in raw &&
    (raw.type === "result" || raw.type === "error")
  );
}

/**
 * useLiveRun streams one message through the real agent. Each server-sent
 * event is validated with Zod and folded into the run state; the live store
 * views are invalidated when the run ends, since it may have booked or routed.
 */
export function useLiveRun() {
  const [run, dispatch] = useReducer(runReducer, initialRun);
  const abort = useRef<AbortController | null>(null);
  const client = useQueryClient();

  async function start(payload: ComposePayload) {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    dispatch({ kind: "start" });
    const seen = { end: false }; // a result or error event arrived (set inside the stream callback)
    try {
      await postEventStream(
        "/api/live/process",
        payload,
        (raw) => {
          const parsed = liveEventSchema.safeParse(raw);
          if (parsed.success) {
            seen.end ||= parsed.data.type === "result" || parsed.data.type === "error";
            dispatch({ kind: "event", event: parsed.data });
          } else if (isTerminal(raw)) {
            seen.end = true;
            dispatch({
              kind: "fail",
              error: "The agent's result could not be read. See the server log.",
            });
          }
        },
        controller.signal,
      );
      if (!seen.end && !controller.signal.aborted) {
        dispatch({
          kind: "fail",
          error: "The connection ended before a result arrived. Try again.",
        });
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      const message =
        error instanceof ApiError && error.status === 422
          ? "The server rejected the message. Check the fields."
          : "Could not reach the agent. Is the console server running?";
      dispatch({ kind: "fail", error: message });
    } finally {
      void client.invalidateQueries({ queryKey: stateKeys.source("live") });
    }
  }

  return { run, start };
}
