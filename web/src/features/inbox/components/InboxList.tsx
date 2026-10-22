import { Link } from "@tanstack/react-router";
import { XCircle } from "lucide-react";

import { clockTime, queueLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

import type { DatasetId, InboxItem } from "../schemas";
import { isCorrect, type InboxFilter } from "../verdict";

const DOT = {
  emergency: "bg-destructive",
  urgent: "bg-warning",
  routine: "bg-transparent",
} as const;
const ROW = "grid grid-cols-12 items-center gap-x-4 gap-y-1 px-4";

/** InboxList: one full-width row per message, like a mail client. Colour only for emergency, urgent and "differs". */
export function InboxList({
  items,
  dataset,
  filter,
}: {
  items: InboxItem[];
  dataset: DatasetId;
  filter: InboxFilter;
}) {
  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <div
        aria-hidden
        className={cn(
          ROW,
          "hidden border-b bg-muted/40 py-2 text-xs text-muted-foreground md:grid",
        )}
      >
        <span className="col-span-1">Time</span>
        <span className="col-span-2">From</span>
        <span className="col-span-5">Message</span>
        <span className="col-span-1">Urgency</span>
        <span className="col-span-2">Routed to</span>
        <span className="col-span-1 text-right">Result</span>
      </div>
      <ul aria-label="Messages" className="divide-y">
        {items.map((item) => {
          const r = item.result;
          const ok = isCorrect(item);
          return (
            <li key={item.message.id}>
              <Link
                to="/inbox/$messageId"
                params={{ messageId: item.message.id }}
                search={{ dataset, filter }}
                className={cn(
                  ROW,
                  "py-3 text-sm transition-colors hover:bg-accent/50 focus-visible:bg-accent focus-visible:outline-none",
                )}
              >
                <span className="col-span-3 flex items-center gap-2 text-xs text-muted-foreground tabular-nums md:col-span-1">
                  <span
                    aria-hidden
                    className={cn("size-2 shrink-0 rounded-full", r && DOT[r.urgency])}
                  />
                  {clockTime(item.message.received_at)}
                </span>
                <span className="col-span-9 truncate font-medium md:col-span-2">
                  {item.message.from_name}
                  <span className="ml-2 font-mono text-xs font-normal text-muted-foreground">
                    {item.message.id}
                  </span>
                </span>
                <span className="col-span-12 truncate text-muted-foreground md:col-span-5">
                  {item.message.body}
                </span>
                <span
                  className={cn(
                    "col-span-4 text-xs capitalize md:col-span-1",
                    r?.urgency === "emergency" && "font-medium text-destructive",
                    r?.urgency === "urgent" && "font-medium",
                    r?.urgency === "routine" && "text-muted-foreground",
                  )}
                >
                  {r?.urgency ?? "not run"}
                </span>
                <span className="col-span-5 truncate text-xs text-muted-foreground md:col-span-2">
                  {r ? r.routed_to.map(queueLabel).join(", ") || "No queue" : ""}
                </span>
                <span className="col-span-3 flex justify-end text-xs md:col-span-1">
                  {ok === null ? (
                    <span className="text-muted-foreground">not scored</span>
                  ) : ok ? (
                    <span className="sr-only">Matches label</span>
                  ) : (
                    <span className="flex items-center gap-1 text-destructive">
                      <XCircle aria-hidden className="size-3.5" />
                      differs
                    </span>
                  )}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
