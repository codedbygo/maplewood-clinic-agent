import { TriangleAlert } from "lucide-react";

import type { Stability } from "../schemas";

/**
 * StabilityCard shows how many messages changed outcome across repeated runs, and which model
 * that measured. A result from another model (or an unlabelled one) is called out, never shown as current.
 */
export function StabilityCard({ stability, model }: { stability: Stability; model: string }) {
  const matches = stability.model === model;
  return (
    <div className="space-y-2 text-sm">
      <p>
        <span className="text-2xl font-semibold tabular-nums">{stability.changed}</span> of{" "}
        {stability.messages} messages changed outcome across {stability.runs} runs
        {stability.changed_ids.length > 0 && (
          <span className="text-muted-foreground"> ({stability.changed_ids.join(", ")})</span>
        )}
        . Emergency decisions that flipped:{" "}
        {stability.emergency_flips.length ? stability.emergency_flips.join(", ") : "none"}.
      </p>
      {stability.model && <p className="text-muted-foreground">Measured with {stability.model}.</p>}
      {!matches && (
        <p className="flex items-start gap-2 rounded-md border border-warning bg-warning/10 p-2">
          <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          {stability.model
            ? `This was measured with ${stability.model}, so it does not describe this run (${model}). Run make stability.`
            : "This file does not record which model it measured, so it does not describe this run. Run make stability."}
        </p>
      )}
      {matches && stability.complete === false && (
        <p className="flex items-start gap-2 rounded-md border border-warning bg-warning/10 p-2">
          <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          Incomplete: at least one run stopped early (daily quota), so unprocessed messages were not
          compared.
        </p>
      )}
    </div>
  );
}
