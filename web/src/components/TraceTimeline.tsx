import {
  CalendarCheck,
  CheckCircle2,
  Flag,
  type LucideIcon,
  MessageSquare,
  Pill,
  Search,
  Send,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";

import type { TraceCall } from "@/features/inbox/schemas";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  verify_sender: ShieldCheck,
  find_patient: Search,
  get_patient_summary: Search,
  list_medications: Pill,
  check_refill_eligibility: Pill,
  prepare_refill_for_approval: Pill,
  get_patient_appointments: CalendarCheck,
  find_available_slots: CalendarCheck,
  book_appointment: CalendarCheck,
  reschedule_appointment: CalendarCheck,
  cancel_appointment: CalendarCheck,
  route_to_queue: Send,
  flag_suspicious_instruction: Flag,
  draft_reply: MessageSquare,
};

const HIDDEN_INPUTS = new Set(["verification_token", "text"]);

function argSummary(input: Record<string, unknown>): string {
  return Object.entries(input)
    .filter(([k, v]) => !HIDDEN_INPUTS.has(k) && v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
}

function outcome(call: TraceCall): string {
  const out = call.output;
  const pick = (k: string) => (typeof out[k] === "string" ? out[k] : undefined);
  return pick("decision") ?? pick("status") ?? (call.ok ? "ok" : "refused");
}

/** TraceTimeline lists the real MCP tool calls in order, each expandable to its full output. */
export function TraceTimeline({ calls, live = false }: { calls: TraceCall[]; live?: boolean }) {
  if (calls.length === 0) {
    return <p className="text-sm text-muted-foreground">No tool calls.</p>;
  }
  return (
    <ol
      aria-label="Tool calls"
      aria-live={live ? "polite" : undefined}
      className="relative space-y-2 border-l pl-5"
    >
      {calls.map((call, i) => {
        const Icon = ICONS[call.name] ?? Wrench;
        const reason = typeof call.output.reason === "string" ? call.output.reason : "";
        return (
          // Calls are append-only and never reorder, so the position is a stable identity.
          <li key={`${String(i)}-${call.name}`} className="relative">
            <span
              aria-hidden
              className={cn(
                "absolute top-2 -left-7 flex size-3.5 items-center justify-center rounded-full border-2 bg-background",
                call.ok ? "border-success" : "border-destructive",
              )}
            />
            <details className="group rounded-md border bg-card px-3 py-2 open:shadow-sm">
              <summary className="flex cursor-pointer list-none items-center gap-2 text-sm">
                <Icon aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                <span className="font-mono font-medium">{call.name}</span>
                <span className="truncate text-muted-foreground">{argSummary(call.input)}</span>
                <span
                  className={cn(
                    "ml-auto flex shrink-0 items-center gap-1 text-xs font-medium",
                    call.ok ? "text-success" : "text-destructive",
                  )}
                >
                  {call.ok ? (
                    <CheckCircle2 aria-hidden className="size-3.5" />
                  ) : (
                    <XCircle aria-hidden className="size-3.5" />
                  )}
                  {outcome(call)}
                </span>
              </summary>
              {reason && (
                <p className="mt-2 text-sm whitespace-pre-line text-muted-foreground">{reason}</p>
              )}
              <pre className="mt-2 max-h-64 overflow-auto rounded bg-muted p-2 text-xs">
                {JSON.stringify({ input: call.input, output: call.output }, null, 2)}
              </pre>
            </details>
          </li>
        );
      })}
    </ol>
  );
}
