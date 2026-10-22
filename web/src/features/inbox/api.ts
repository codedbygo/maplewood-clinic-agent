import { apiFetch } from "@/lib/api";

import {
  datasetListSchema,
  healthSchema,
  inboxResponseSchema,
  type Dataset,
  type DatasetId,
  type Health,
  type InboxResponse,
} from "./schemas";

type Init = Pick<RequestInit, "signal">;

/** GET /api/health: model in use and whether an API key is configured. */
export function fetchHealth(init: Init = {}): Promise<Health> {
  return apiFetch("/api/health", healthSchema, init);
}

/** GET /api/datasets: the message sets and whether each has a run and an evaluation. */
export function fetchDatasets(init: Init = {}): Promise<Dataset[]> {
  return apiFetch("/api/datasets", datasetListSchema, init);
}

/** GET /api/datasets/:id/inbox: every message joined with its label, result, run log and score. */
export function fetchInbox(dataset: DatasetId, init: Init = {}): Promise<InboxResponse> {
  return apiFetch(`/api/datasets/${dataset}/inbox`, inboxResponseSchema, init);
}
