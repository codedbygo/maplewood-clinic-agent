import { Link } from "@tanstack/react-router";
import {
  CheckCircle2,
  Mail,
  MessageCircle,
  Monitor,
  Play,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import type { ReactNode } from "react";

import { ChipList } from "@/components/ChipList";
import { ReplyCard } from "@/components/ReplyCard";
import { TraceTimeline } from "@/components/TraceTimeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { UrgencyBadge } from "@/components/UrgencyBadge";
import { splitRootCause } from "@/features/eval/rootCause";
import { usePatientNames } from "@/features/state/hooks";
import { actionLabel, clockTime, label, queueLabel, seconds } from "@/lib/format";
import { cn } from "@/lib/utils";

import type { DatasetId, InboxItem } from "../schemas";
import { isCorrect } from "../verdict";

const CHANNEL_ICON = { sms: MessageCircle, portal: Monitor, email: Mail } as const;

function ChannelIcon({ channel }: { channel: string }) {
  const Icon =
    channel === "sms" || channel === "portal" || channel === "email"
      ? CHANNEL_ICON[channel]
      : MessageCircle;
  return <Icon aria-hidden className="size-4 text-muted-foreground" />;
}

function Mark({ ok }: { ok: boolean | undefined }) {
  if (ok === undefined) return null;
  return ok ? (
    <CheckCircle2 aria-label="Matches" className="size-4 text-success" />
  ) : (
    <XCircle aria-label="Differs" className="size-4 text-destructive" />
  );
}

/** Verdict: why a message differs from its label, as one quiet line above the comparison. */
function Verdict({ rootCause }: { rootCause: string | null | undefined }) {
  const { category, detail } = splitRootCause(rootCause ?? undefined);
  return (
    <p className="border-l-2 border-warning pl-3 text-sm text-muted-foreground">
      <span className="font-medium text-foreground">{category}.</span> {detail}
    </p>
  );
}

/** Comparison: the agent's output beside the label, one row per field, so a difference is one glance. */
function Comparison({ item, patientName }: { item: InboxItem; patientName: string | undefined }) {
  const { result, label: expected, score } = item;
  const rows: { field: string; agent: ReactNode; label: ReactNode; ok?: boolean | undefined }[] = [
    {
      field: "Urgency",
      agent: result ? <UrgencyBadge urgency={result.urgency} /> : null,
      label: expected?.accepted_urgency.join(" or "),
      ok: score?.urgency_ok,
    },
    {
      field: "Patient",
      agent: result?.patient_id ? (
        <span>
          <span className="font-mono">{result.patient_id}</span>
          {patientName && <span className="text-muted-foreground"> · {patientName}</span>}
        </span>
      ) : (
        <span className="text-muted-foreground">null (not verified)</span>
      ),
      label: <span className="font-mono">{expected?.patient_id ?? "null"}</span>,
      ok: score?.patient_ok,
    },
    {
      field: "Intents",
      agent: result && <ChipList label="Agent intents" items={result.intents} format={label} />,
      label: expected && (
        <ChipList label="Expected intents" items={expected.intents} format={label} />
      ),
      ok: score ? score.intent_f1 === 1 : undefined,
    },
    {
      field: "Actions",
      agent: result && (
        <ChipList
          label="Agent actions"
          items={result.actions}
          format={actionLabel}
          missing={score?.missing_actions ?? []}
          extra={score?.extra_actions ?? []}
        />
      ),
      label: expected && (
        <ChipList label="Expected actions" items={expected.expected_actions} format={actionLabel} />
      ),
      ok: score?.actions_exact,
    },
    {
      field: "Routed to",
      agent: result && (
        <ChipList
          label="Queues"
          items={result.routed_to}
          format={queueLabel}
          emptyText="No human queue"
        />
      ),
      label: <span className="text-muted-foreground">Implied by the actions</span>,
      ok: score?.routing_ok,
    },
  ];
  if (expected?.must_not.length)
    rows.push({
      field: "Must not",
      agent: <span className="text-muted-foreground">Checked by the evaluation</span>,
      label: <ChipList label="Must not" items={expected.must_not} format={label} />,
    });

  return (
    <table aria-label="Agent and label" className="w-full text-sm">
      <thead className="text-left text-xs text-muted-foreground">
        <tr>
          <th className="w-24 pb-2 font-medium">Field</th>
          <th className="pb-2 font-medium">Agent</th>
          <th className="pb-2 font-medium">Label</th>
          <th className="w-8 pb-2">
            <span className="sr-only">Result</span>
          </th>
        </tr>
      </thead>
      <tbody className="divide-y align-top">
        {rows.map((row) => (
          <tr key={row.field}>
            <th
              scope="row"
              className={cn(
                "py-2.5 pr-3 text-left font-normal text-muted-foreground",
                row.ok === false && "font-medium text-destructive",
              )}
            >
              {row.field}
            </th>
            <td className="py-2.5 pr-3">
              {row.agent ?? <span className="text-muted-foreground">Not processed</span>}
            </td>
            <td className="py-2.5 pr-3">
              {row.label ?? <span className="text-muted-foreground">No label</span>}
            </td>
            <td className="py-2.5">
              <Mark ok={row.ok} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** MessageDetail: the message, what the agent did, what the label expected, and the full trace. */
export function MessageDetail({ item, dataset }: { item: InboxItem; dataset: DatasetId }) {
  const names = usePatientNames();
  const { message, result, label: expected, log } = item;
  const ok = isCorrect(item);
  const calls = log?.trace?.length ?? 0;
  return (
    <Card className="gap-0 py-0">
      <article aria-labelledby="detail-title">
        <header className="space-y-3 border-b p-5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <ChannelIcon channel={message.channel} />
            <h2 id="detail-title" className="text-base font-semibold">
              {message.from_name}
            </h2>
            <span className="text-sm text-muted-foreground">{message.from_contact}</span>
            <span className="ml-auto font-mono text-xs text-muted-foreground">
              {message.id} · {clockTime(message.received_at)}
            </span>
            <Button asChild variant="outline" size="sm">
              <Link to="/" search={{ replay: message.id, dataset }}>
                <Play aria-hidden />
                Re-run live
              </Link>
            </Button>
          </div>
          <blockquote className="text-sm whitespace-pre-line">{message.body}</blockquote>
          {(message.stated_dob ?? expected?.trap) && (
            <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
              <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
              <span>
                {message.stated_dob && <>Stated date of birth {message.stated_dob}. </>}
                {expected?.trap && <>Why it is tricky: {expected.trap}</>}
              </span>
            </p>
          )}
        </header>

        {result && (
          <div className="flex flex-wrap items-center gap-2 border-b bg-muted/40 px-5 py-3 text-sm">
            <UrgencyBadge urgency={result.urgency} />
            <span className="text-muted-foreground">to</span>
            <ChipList
              label="Routed to"
              items={result.routed_to}
              format={queueLabel}
              emptyText="no human queue"
            />
            {ok !== null && (
              <span
                className={cn(
                  "ml-auto flex items-center gap-1.5 text-xs font-medium",
                  ok ? "text-success" : "text-destructive",
                )}
              >
                {ok ? (
                  <CheckCircle2 aria-hidden className="size-4" />
                ) : (
                  <XCircle aria-hidden className="size-4" />
                )}
                {ok ? "Matches the label" : "Differs from the label"}
              </span>
            )}
          </div>
        )}

        <Tabs defaultValue="outcome" className="gap-4 p-5">
          <TabsList>
            <TabsTrigger value="outcome">Outcome</TabsTrigger>
            <TabsTrigger value="trace" disabled={!log}>
              Trace{calls ? ` (${String(calls)} calls)` : ""}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="outcome" className="space-y-4">
            {ok === false && <Verdict rootCause={item.root_cause} />}
            <Comparison
              item={item}
              patientName={result?.patient_id ? names.data?.get(result.patient_id) : undefined}
            />
            {result && (
              <ReplyCard
                text={result.reply_draft}
                emergency={result.actions.includes("escalate_emergency")}
              />
            )}
          </TabsContent>
          {log && (
            <TabsContent value="trace" className="space-y-3">
              <p className="flex flex-wrap items-center gap-2 text-xs">
                {log.path && (
                  <Badge variant={log.path === "emergency" ? "destructive" : "outline"}>
                    {log.path} path
                  </Badge>
                )}
                {log.screen && log.screen.tier !== "none" && (
                  <Badge variant="outline">
                    pre-screen: {label(log.screen.tier)} ({log.screen.matches.join(", ")})
                  </Badge>
                )}
                {typeof log.latency_s === "number" && (
                  <span className="ml-auto text-muted-foreground">{seconds(log.latency_s)}</span>
                )}
              </p>
              {log.triage && (
                <p className="text-sm text-muted-foreground">Triage: {log.triage.rationale}</p>
              )}
              <TraceTimeline calls={log.trace ?? []} />
              {log.guard_violations && log.guard_violations.length > 0 && (
                <div className="border-l-2 border-warning pl-3 text-sm">
                  <p className="font-medium">Post-guard corrections</p>
                  <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                    {log.guard_violations.map((g) => (
                      <li key={g}>{g}</li>
                    ))}
                  </ul>
                </div>
              )}
            </TabsContent>
          )}
        </Tabs>
      </article>
    </Card>
  );
}
