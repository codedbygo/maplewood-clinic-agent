import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: string;
  hint?: ReactNode;
  tone?: "default" | "good" | "bad";
  emphasis?: boolean;
}

/** StatTile shows one metric with an optional hint line. */
export function StatTile({ label, value, hint, tone = "default", emphasis = false }: Props) {
  return (
    <Card className={cn("gap-1 py-4", emphasis && "border-primary/40 bg-accent/40")}>
      <CardContent className="space-y-1 px-4">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</p>
        <p
          className={cn(
            "font-semibold tabular-nums",
            emphasis ? "text-3xl" : "text-2xl",
            tone === "good" && "text-success",
            tone === "bad" && "text-destructive",
          )}
        >
          {value}
        </p>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}
