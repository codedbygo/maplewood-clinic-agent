import { Flag, Pill } from "lucide-react";

import { PageHeader } from "@/components/PageHeader";
import { Pending, QueryError } from "@/components/QueryState";
import { Segmented } from "@/components/Segmented";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useClinicState, usePatientNames } from "@/features/state/hooks";
import type { QueueRoute, StateSource } from "@/features/state/schemas";
import { SOURCES } from "@/features/state/sources";
import { QUEUE_ORDER, queueLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

const PRIORITY_STYLE: Record<string, string> = {
  emergency: "border-transparent bg-destructive text-white",
  urgent: "border-transparent bg-warning text-foreground",
};

function RouteCard({ route, patient }: { route: QueueRoute; patient: string | undefined }) {
  return (
    <li
      className={cn(
        "rounded-md border bg-card p-3 text-sm",
        route.priority === "emergency" && "border-destructive",
      )}
    >
      <div className="mb-1 flex items-center gap-2">
        <Badge variant="outline" className={cn("capitalize", PRIORITY_STYLE[route.priority])}>
          {route.priority}
        </Badge>
        {route.message_id && (
          <span className="font-mono text-xs whitespace-nowrap text-muted-foreground">
            {route.message_id}
          </span>
        )}
        {patient && (
          <span className="ml-auto truncate text-xs text-muted-foreground">{patient}</span>
        )}
      </div>
      <p className="line-clamp-4 break-words whitespace-pre-line">{route.summary}</p>
    </li>
  );
}

/** QueuesPage: what each human queue received, plus pending refill requests and flagged instructions. */
export function QueuesPage({
  source,
  onSource,
}: {
  source: StateSource;
  onSource: (s: StateSource) => void;
}) {
  const state = useClinicState(source);
  const names = usePatientNames();
  const nameOf = (id: string | null | undefined) => (id ? names.data?.get(id) : undefined);

  let body;
  if (state.isPending) body = <Pending label="Loading queues" />;
  else if (state.isError)
    body = (
      <QueryError
        error={state.error}
        onRetry={() => void state.refetch()}
        notFound={
          <p>This run has not produced a store yet. Run it first (make run or make holdout).</p>
        }
      />
    );
  else {
    const { routes, refill_requests: refills, flags } = state.data;
    body = (
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {QUEUE_ORDER.map((queue) => {
            const items = routes.filter((r) => r.queue === queue);
            return (
              <section key={queue} aria-label={queueLabel(queue)} className="space-y-2">
                <h2 className="flex items-center justify-between text-sm font-semibold">
                  {queueLabel(queue)}
                  <Badge variant="secondary">{items.length}</Badge>
                </h2>
                {items.length ? (
                  <ul className="space-y-2">
                    {items.map((r, i) => (
                      <RouteCard
                        key={`${r.message_id ?? "x"}-${String(i)}`}
                        route={r}
                        patient={nameOf(r.patient_id)}
                      />
                    ))}
                  </ul>
                ) : (
                  <p className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
                    Empty
                  </p>
                )}
              </section>
            );
          })}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="gap-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Pill aria-hidden className="size-4" /> Refill requests awaiting provider approval (
                {refills.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {refills.length ? (
                <ul className="divide-y text-sm">
                  {refills.map((q) => (
                    <li key={q.id} className="flex flex-wrap items-center gap-2 py-2">
                      <span className="font-medium">{q.medication}</span>
                      <span className="text-muted-foreground">
                        {nameOf(q.patient_id) ?? q.patient_id}
                      </span>
                      <Badge variant="outline" className="ml-auto">
                        {q.status.replace(/_/g, " ")}
                      </Badge>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">
                  None. The agent never approves; it only prepares requests.
                </p>
              )}
            </CardContent>
          </Card>
          <Card className="gap-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Flag aria-hidden className="size-4" /> Flagged instructions ({flags.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {flags.length ? (
                <ul className="space-y-2 text-sm">
                  {flags.map((f, i) => (
                    <li
                      key={`${f.message_id ?? "x"}-${String(i)}`}
                      className="rounded-md border p-2"
                    >
                      <q className="italic">{f.excerpt}</q>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {f.message_id} · {f.why}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No suspicious instructions flagged.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Staff queues"
        description="The clinic's side: what landed in each human queue, and why."
      >
        <Segmented label="Data source" value={source} onChange={onSource} options={SOURCES} />
      </PageHeader>
      {body}
    </div>
  );
}
