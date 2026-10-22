import { queryOptions, useQuery } from "@tanstack/react-query";

import { fetchDatasets, fetchHealth, fetchInbox } from "./api";
import type { DatasetId } from "./schemas";

export const inboxKeys = {
  all: ["inbox"] as const,
  health: () => [...inboxKeys.all, "health"] as const,
  datasets: () => [...inboxKeys.all, "datasets"] as const,
  dataset: (id: DatasetId) => [...inboxKeys.all, "dataset", id] as const,
};

export function healthQueryOptions() {
  return queryOptions({
    queryKey: inboxKeys.health(),
    queryFn: ({ signal }) => fetchHealth({ signal }),
  });
}

export function datasetsQueryOptions() {
  return queryOptions({
    queryKey: inboxKeys.datasets(),
    queryFn: ({ signal }) => fetchDatasets({ signal }),
  });
}

export function inboxQueryOptions(dataset: DatasetId) {
  return queryOptions({
    queryKey: inboxKeys.dataset(dataset),
    queryFn: ({ signal }) => fetchInbox(dataset, { signal }),
  });
}

export function useHealth() {
  return useQuery(healthQueryOptions());
}

export function useInbox(dataset: DatasetId) {
  return useQuery(inboxQueryOptions(dataset));
}
