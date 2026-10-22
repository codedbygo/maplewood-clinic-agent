import { queryOptions, useQuery } from "@tanstack/react-query";

import type { DatasetId } from "@/features/inbox/schemas";

import { fetchEvalReport, fetchStability } from "./api";

export const evalKeys = {
  all: ["eval"] as const,
  report: (dataset: DatasetId) => [...evalKeys.all, "report", dataset] as const,
  stability: () => [...evalKeys.all, "stability"] as const,
};

export function evalReportQueryOptions(dataset: DatasetId) {
  return queryOptions({
    queryKey: evalKeys.report(dataset),
    queryFn: ({ signal }) => fetchEvalReport(dataset, { signal }),
  });
}

export function stabilityQueryOptions() {
  return queryOptions({
    queryKey: evalKeys.stability(),
    queryFn: ({ signal }) => fetchStability({ signal }),
  });
}

export function useEvalReport(dataset: DatasetId) {
  return useQuery(evalReportQueryOptions(dataset));
}

export function useStability() {
  return useQuery(stabilityQueryOptions());
}
