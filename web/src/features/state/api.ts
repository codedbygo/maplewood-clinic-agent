import { z } from "zod";

import { apiFetch } from "@/lib/api";

import {
  clinicInfoSchema,
  clinicStateSchema,
  type ClinicInfo,
  type ClinicState,
  type StateSource,
} from "./schemas";

type Init = Pick<RequestInit, "signal">;

/** The live session's store, or the final store of the latest dataset run. */
export function fetchClinicState(source: StateSource, init: Init = {}): Promise<ClinicState> {
  const path = source === "live" ? "/api/live/state" : `/api/datasets/${source}/state`;
  return apiFetch(path, clinicStateSchema, init);
}

/** GET /api/clinic: hours, holidays, providers with leave, and patient names for display. */
export function fetchClinicInfo(init: Init = {}): Promise<ClinicInfo> {
  return apiFetch("/api/clinic", clinicInfoSchema, init);
}

/** POST /api/live/reset: restore the live session's store to the JSON files. */
export function resetLiveState(): Promise<{ ok: boolean }> {
  return apiFetch("/api/live/reset", z.object({ ok: z.boolean() }), { method: "POST" });
}
