import { PageHeader } from "@/components/PageHeader";
import { Empty, Pending, QueryError } from "@/components/QueryState";
import { Segmented } from "@/components/Segmented";
import { Badge } from "@/components/ui/badge";

import { useInbox } from "../hooks";
import type { DatasetId, InboxItem } from "../schemas";
import { isCorrect } from "../verdict";
import { InboxList } from "./InboxList";
import { MessageDetail } from "./MessageDetail";

export type InboxFilter = "all" | "attention" | "emergency";

export interface InboxSearch {
  dataset: DatasetId;
  id?: string | undefined;
  filter: InboxFilter;
}

const DATASETS: { value: DatasetId; label: string }[] = [
  { value: "sample", label: "Sample (40)" },
  { value: "holdout", label: "Held-out (13)" },
];

function applyFilter(items: InboxItem[], filter: InboxFilter): InboxItem[] {
  if (filter === "attention") return items.filter((i) => isCorrect(i) === false);
  if (filter === "emergency")
    return items.filter(
      (i) =>
        (i.result?.actions.includes("escalate_emergency") ?? false) ||
        (i.label?.expected_actions.includes("escalate_emergency") ?? false),
    );
  return items;
}

/** InboxPage: every message of a dataset run, filterable, with full detail for the selected one. */
export function InboxPage({
  search,
  onSearch,
}: {
  search: InboxSearch;
  onSearch: (next: Partial<InboxSearch>) => void;
}) {
  const inbox = useInbox(search.dataset);

  let body;
  if (inbox.isPending) body = <Pending label="Loading messages" />;
  else if (inbox.isError)
    body = <QueryError error={inbox.error} onRetry={() => void inbox.refetch()} />;
  else {
    const all = inbox.data.items;
    const items = applyFilter(all, search.filter);
    const wrong = all.filter((i) => isCorrect(i) === false).length;
    const emergencies = applyFilter(all, "emergency").length;
    const selected = items.find((i) => i.message.id === search.id) ?? items[0];
    body = (
      <div className="space-y-4">
        {!inbox.data.run && (
          <Empty title="No run for this dataset yet">
            Run <code className="rounded bg-muted px-1">make run</code> (sample) or{" "}
            <code className="rounded bg-muted px-1">make holdout</code>, then reload. Messages are
            listed below without results.
          </Empty>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <Segmented
            label="Filter messages"
            value={search.filter}
            onChange={(filter) => {
              onSearch({ filter, id: undefined });
            }}
            options={[
              { value: "all", label: `All (${String(all.length)})` },
              { value: "attention", label: `Differs from label (${String(wrong)})` },
              { value: "emergency", label: `Emergencies (${String(emergencies)})` },
            ]}
          />
          {inbox.data.run && (
            <Badge variant="outline" className="font-normal text-muted-foreground">
              Run {inbox.data.run.run_id} · {inbox.data.run.model}
            </Badge>
          )}
        </div>
        {items.length === 0 ? (
          <Empty title="No messages match this filter" />
        ) : (
          <div className="grid gap-4 lg:grid-cols-5">
            <nav aria-label="Message list" className="lg:col-span-2">
              <InboxList
                items={items}
                selectedId={selected?.message.id}
                onSelect={(id) => {
                  onSearch({ id });
                }}
              />
            </nav>
            <section aria-label="Message detail" className="lg:col-span-3">
              {selected && <MessageDetail key={selected.message.id} item={selected} />}
            </section>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inbox"
        description="Each message with the agent's result, the label, and the real tool trace."
      >
        <Segmented
          label="Dataset"
          value={search.dataset}
          onChange={(dataset) => {
            onSearch({ dataset, id: undefined, filter: "all" });
          }}
          options={DATASETS}
        />
      </PageHeader>
      {body}
    </div>
  );
}
