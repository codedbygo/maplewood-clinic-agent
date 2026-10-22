import { AlertTriangle, Clock, Siren } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Urgency } from "@/features/inbox/schemas";
import { cn } from "@/lib/utils";

const STYLE: Record<Urgency, string> = {
  emergency: "border-transparent bg-destructive text-white",
  urgent: "border-transparent bg-warning text-foreground",
  routine: "border-border bg-muted text-muted-foreground",
};

const ICON = { emergency: Siren, urgent: AlertTriangle, routine: Clock } as const;

/** UrgencyBadge shows urgency by colour, icon and word, so it never relies on colour alone. */
export function UrgencyBadge({ urgency, className }: { urgency: Urgency; className?: string }) {
  const Icon = ICON[urgency];
  return (
    <Badge variant="outline" className={cn("gap-1 capitalize", STYLE[urgency], className)}>
      <Icon aria-hidden className="size-3" />
      {urgency}
    </Badge>
  );
}
