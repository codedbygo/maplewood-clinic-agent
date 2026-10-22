import { MessageSquareText } from "lucide-react";

import { cn } from "@/lib/utils";

/** ReplyCard shows the drafted reply as plain text (it is untrusted model output). */
export function ReplyCard({ text, emergency = false }: { text: string; emergency?: boolean }) {
  return (
    <figure
      className={cn(
        "rounded-lg border p-4",
        emergency ? "border-destructive/50 bg-destructive/5" : "border-primary/30 bg-accent/30",
      )}
    >
      <figcaption className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <MessageSquareText aria-hidden className="size-4" />
        Draft reply (held for staff review)
      </figcaption>
      {text ? (
        <p className="text-sm whitespace-pre-line">{text}</p>
      ) : (
        <p className="text-sm text-muted-foreground italic">No reply drafted (no action).</p>
      )}
    </figure>
  );
}
