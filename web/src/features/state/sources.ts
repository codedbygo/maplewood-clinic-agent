import type { StateSource } from "./schemas";

/** The stores a staff view can show: the live session, or the final state of a dataset run. */
export const SOURCES: { value: StateSource; label: string }[] = [
  { value: "live", label: "Live session" },
  { value: "sample", label: "Sample run" },
  { value: "holdout", label: "Held-out run" },
];
