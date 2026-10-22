import { CheckCircle2, CircleDashed, Siren, XCircle } from "lucide-react";

import { UrgencyBadge } from "@/components/UrgencyBadge";
import { clockTime } from "@/lib/format";
import { cn } from "@/lib/utils";

import type { InboxItem } from "../schemas";
import { isCorrect } from "../verdict";

function Verdict({ item }: { item: InboxItem }) {
  const ok = isCorrect(item);
  if (ok === null)
    return <CircleDashed aria-label="Not scored" className="size-4 text-muted-foreground" />;
  return ok ? (
    <CheckCircle2 aria-label="Matches label" className="size-4 text-success" />
  ) : (
    <XCircle aria-label="Differs from label" className="size-4 text-destructive" />
  );
}

interface Props {
  items: InboxItem[];
  selectedId: string | undefined;
  onSelect: (id: string) => void;
}

/** InboxList: messages in arrival order, emergencies marked, each with its verdict against the label. */
export function InboxList({ items, selectedId, onSelect }: Props) {
  return (
    <ul aria-label="Messages" className="divide-y overflow-hidden rounded-lg border">
      {items.map((item) => {
        const r = item.result;
        const emergency = r?.actions.includes("escalate_emergency") ?? false;
        const selected = item.message.id === selectedId;
        return (
          <li key={item.message.id}>
            <button
              type="button"
              aria-current={selected ? "true" : undefined}
              onClick={() => {
                onSelect(item.message.id);
              }}
              className={cn(
                "flex w-full flex-col gap-1 px-3 py-2.5 text-left transition-colors hover:bg-accent/50 focus-visible:bg-accent focus-visible:outline-none",
                selected && "bg-accent",
                emergency && "border-l-4 border-l-destructive",
              )}
            >
              <span className="flex items-center gap-2 text-sm">
                <span className="font-mono text-xs text-muted-foreground">{item.message.id}</span>
                <span className="truncate font-medium">{item.message.from_name}</span>
                {emergency && (
                  <Siren aria-label="Emergency" className="size-4 shrink-0 text-destructive" />
                )}
                <span className="ml-auto flex shrink-0 items-center gap-2">
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {clockTime(item.message.received_at)}
                  </span>
                  <Verdict item={item} />
                </span>
              </span>
              <span className="line-clamp-1 text-sm text-muted-foreground">
                {item.message.body}
              </span>
              {r && <UrgencyBadge urgency={r.urgency} className="w-fit" />}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
