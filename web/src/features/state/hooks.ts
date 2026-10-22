import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchClinicInfo, fetchClinicState, resetLiveState } from "./api";
import type { StateSource } from "./schemas";

export const stateKeys = {
  all: ["state"] as const,
  source: (source: StateSource) => [...stateKeys.all, "source", source] as const,
  clinic: () => [...stateKeys.all, "clinic"] as const,
};

export function clinicStateQueryOptions(source: StateSource) {
  return queryOptions({
    queryKey: stateKeys.source(source),
    queryFn: ({ signal }) => fetchClinicState(source, { signal }),
  });
}

export function clinicInfoQueryOptions() {
  return queryOptions({
    queryKey: stateKeys.clinic(),
    queryFn: ({ signal }) => fetchClinicInfo({ signal }),
    staleTime: Infinity,
  });
}

export function useClinicState(source: StateSource) {
  return useQuery(clinicStateQueryOptions(source));
}

export function useClinicInfo() {
  return useQuery(clinicInfoQueryOptions());
}

/** Patient id to display name, for staff views. */
export function usePatientNames() {
  return useQuery({
    ...clinicInfoQueryOptions(),
    select: (info) => new Map(info.patients.map((p) => [p.id, p.name])),
  });
}

export function useResetLiveState() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: resetLiveState,
    onSuccess: () => client.invalidateQueries({ queryKey: stateKeys.source("live") }),
  });
}
