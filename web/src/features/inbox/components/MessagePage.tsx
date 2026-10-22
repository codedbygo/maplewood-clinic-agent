import { Link } from "@tanstack/react-router";
import { ArrowLeft, ChevronLeft, ChevronRight } from "lucide-react";

import { Empty, Pending, QueryError } from "@/components/QueryState";
import { Button } from "@/components/ui/button";

import { useInbox } from "../hooks";
import type { DatasetId } from "../schemas";
import { applyFilter, type InboxFilter } from "../verdict";
import { MessageDetail } from "./MessageDetail";

/**
 * MessagePage: one message on its own page. Previous and next step through the list the user came
 * from (the same filter), so reviewing "Differs from label" is one click per case.
 */
export function MessagePage({
  messageId,
  dataset,
  filter,
}: {
  messageId: string;
  dataset: DatasetId;
  filter: InboxFilter;
}) {
  const inbox = useInbox(dataset);
  const back = (
    <Link
      to="/inbox"
      search={{ dataset, filter }}
      aria-label="Back to inbox"
      className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft aria-hidden className="size-4" />
      Inbox
    </Link>
  );

  if (inbox.isPending) return <Pending label="Loading message" />;
  if (inbox.isError) return <QueryError error={inbox.error} onRetry={() => void inbox.refetch()} />;

  const filtered = applyFilter(inbox.data.items, filter);
  // A message outside the filter (a pasted link) still opens; it steps through all messages instead.
  const list = filtered.some((i) => i.message.id === messageId) ? filtered : inbox.data.items;
  const at = list.findIndex((i) => i.message.id === messageId);
  const item = list[at];

  if (!item)
    return (
      <div className="space-y-4">
        {back}
        <Empty title={`No message ${messageId} in this dataset`}>
          It may belong to the other dataset. Go back to the inbox to pick one.
        </Empty>
      </div>
    );

  const prev = list[at - 1];
  const next = list[at + 1];
  const step = (target: typeof prev, label: string, icon: React.ReactNode) =>
    target ? (
      <Button asChild variant="outline" size="sm">
        <Link
          to="/inbox/$messageId"
          params={{ messageId: target.message.id }}
          search={{ dataset, filter }}
          aria-label={`${label}: ${target.message.id}`}
        >
          {icon}
        </Link>
      </Button>
    ) : (
      <Button variant="outline" size="sm" disabled aria-label={label}>
        {icon}
      </Button>
    );

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <nav aria-label="Message navigation" className="flex items-center gap-3">
        {back}
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          {at + 1} of {list.length}
        </span>
        {step(prev, "Previous message", <ChevronLeft aria-hidden />)}
        {step(next, "Next message", <ChevronRight aria-hidden />)}
      </nav>
      <MessageDetail key={item.message.id} item={item} dataset={dataset} />
    </div>
  );
}
