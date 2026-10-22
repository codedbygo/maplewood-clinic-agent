import type { DatasetId } from "@/features/inbox/schemas";
import { apiFetch } from "@/lib/api";

import { evalReportSchema, stabilitySchema, type EvalReport, type Stability } from "./schemas";

type Init = Pick<RequestInit, "signal">;

/** GET /api/datasets/:id/eval: the report `make eval` wrote (404 before the first evaluation). */
export function fetchEvalReport(dataset: DatasetId, init: Init = {}): Promise<EvalReport> {
  return apiFetch(`/api/datasets/${dataset}/eval`, evalReportSchema, init);
}

/** GET /api/stability: how many messages changed outcome across repeated runs. */
export function fetchStability(init: Init = {}): Promise<Stability> {
  return apiFetch("/api/stability", stabilitySchema, init);
}
