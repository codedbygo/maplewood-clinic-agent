import { PageHeader } from "@/components/PageHeader";
import { Empty, Pending, QueryError } from "@/components/QueryState";
import { Segmented } from "@/components/Segmented";

import { useInbox } from "../hooks";
import type { DatasetId } from "../schemas";
import { applyFilter, isCorrect, type InboxFilter } from "../verdict";
import { InboxList } from "./InboxList";

export interface InboxSearch {
  dataset: DatasetId;
  filter: InboxFilter;
}

const DATASETS: { value: DatasetId; label: string }[] = [
  { value: "sample", label: "Sample (40)" },
  { value: "holdout", label: "Held-out (13)" },
];

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
              onSearch({ filter });
            }}
            options={[
              { value: "all", label: `All (${String(all.length)})` },
              { value: "attention", label: `Differs from label (${String(wrong)})` },
              { value: "emergency", label: `Emergencies (${String(emergencies)})` },
            ]}
          />
          {inbox.data.run && (
            <span className="ml-auto text-xs text-muted-foreground">
              Run {inbox.data.run.run_id} · {inbox.data.run.model}
            </span>
          )}
        </div>
        {items.length === 0 ? (
          <Empty title="No messages match this filter" />
        ) : (
          <InboxList items={items} dataset={search.dataset} filter={search.filter} />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inbox"
        description="Every message the agent processed. Open one for its result, the label and the tool trace."
      >
        <Segmented
          label="Dataset"
          value={search.dataset}
          onChange={(dataset) => {
            onSearch({ dataset, filter: "all" });
          }}
          options={DATASETS}
        />
      </PageHeader>
      {body}
    </div>
  );
}
