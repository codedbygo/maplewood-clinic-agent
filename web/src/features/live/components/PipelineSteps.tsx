import { Check, Circle, Loader2, ShieldAlert } from "lucide-react";

import { cn } from "@/lib/utils";

import type { RunState } from "../runReducer";
import { steps } from "../steps";

const ICON = {
  waiting: Circle,
  active: Loader2,
  done: Check,
  alert: ShieldAlert,
  skipped: Circle,
} as const;

/** PipelineSteps: where the message is in the layered pipeline, live. */
export function PipelineSteps({ run }: { run: RunState }) {
  return (
    <ol aria-label="Pipeline" className="grid gap-2 sm:grid-cols-5">
      {steps(run).map((step) => {
        const Icon = ICON[step.status];
        return (
          <li
            key={step.name}
            className={cn(
              "rounded-md border p-2.5 text-sm",
              step.status === "active" && "border-primary bg-accent/50",
              step.status === "done" && "border-success/40",
              step.status === "alert" && "border-destructive/50 bg-destructive/5",
              (step.status === "waiting" || step.status === "skipped") && "text-muted-foreground",
            )}
          >
            <p className="flex items-center gap-1.5 font-medium">
              <Icon
                aria-hidden
                className={cn(
                  "size-4",
                  step.status === "active" && "animate-spin",
                  step.status === "done" && "text-success",
                  step.status === "alert" && "text-destructive",
                )}
              />
              {step.name}
              <span className="sr-only">: {step.status}</span>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{step.detail}</p>
          </li>
        );
      })}
    </ol>
  );
}
