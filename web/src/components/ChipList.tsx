import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface Props {
  items: string[];
  format: (item: string) => string;
  /** Items to mark as missing (expected but not produced) or extra (produced but not expected). */
  missing?: string[];
  extra?: string[];
  emptyText?: string;
  label: string;
}

/** ChipList renders actions, queues or intents as chips, marking differences from the label. */
export function ChipList({
  items,
  format,
  missing = [],
  extra = [],
  emptyText = "None",
  label,
}: Props) {
  const all = [...items, ...missing.filter((m) => !items.includes(m))];
  if (all.length === 0) return <span className="text-sm text-muted-foreground">{emptyText}</span>;
  return (
    <ul aria-label={label} className="flex flex-wrap gap-1.5">
      {all.map((item) => {
        const isMissing = missing.includes(item) && !items.includes(item);
        const isExtra = extra.includes(item);
        return (
          <li key={item}>
            <Badge
              variant="outline"
              className={cn(
                "font-normal",
                isMissing && "border-dashed border-destructive text-destructive",
                isExtra && "border-warning bg-warning/15",
              )}
            >
              {format(item)}
              {isMissing && <span className="sr-only"> (missing)</span>}
              {isExtra && <span className="sr-only"> (not expected)</span>}
            </Badge>
          </li>
        );
      })}
    </ul>
  );
}
