import { Mail, MessageCircle, Monitor, ShieldAlert } from "lucide-react";

import { ChipList } from "@/components/ChipList";
import { ResultSummary } from "@/components/ResultSummary";
import { TraceTimeline } from "@/components/TraceTimeline";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePatientNames } from "@/features/state/hooks";
import { actionLabel, clockTime, label, seconds } from "@/lib/format";

import type { InboxItem } from "../schemas";

const CHANNEL_ICON = { sms: MessageCircle, portal: Monitor, email: Mail } as const;

function ChannelIcon({ channel }: { channel: string }) {
  const Icon =
    channel === "sms" || channel === "portal" || channel === "email"
      ? CHANNEL_ICON[channel]
      : MessageCircle;
  return <Icon aria-hidden className="size-4 text-muted-foreground" />;
}

/** MessageDetail: the message, what the agent did, what the label expected, and the full trace. */
export function MessageDetail({ item }: { item: InboxItem }) {
  const names = usePatientNames();
  const { message, result, label: expected, log, score } = item;
  return (
    <article aria-labelledby="detail-title" className="space-y-4">
      <Card className="gap-3">
        <CardHeader>
          <h2
            id="detail-title"
            className="flex flex-wrap items-center gap-2 text-base leading-none font-semibold"
          >
            <ChannelIcon channel={message.channel} />
            {message.from_name}
            <span className="font-normal text-muted-foreground">{message.from_contact}</span>
            <span className="ml-auto font-mono text-xs font-normal text-muted-foreground">
              {message.id} · {clockTime(message.received_at)}
            </span>
          </h2>
        </CardHeader>
        <CardContent className="space-y-2">
          <blockquote className="rounded-md bg-muted p-3 text-sm whitespace-pre-line">
            {message.body}
          </blockquote>
          {message.stated_dob && (
            <p className="text-xs text-muted-foreground">
              Stated date of birth: {message.stated_dob}
            </p>
          )}
          {expected?.trap && (
            <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
              <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
              <span>
                <span className="font-medium">Why it is tricky:</span> {expected.trap}
              </span>
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="gap-3">
          <CardHeader>
            <CardTitle className="text-base">What the agent did</CardTitle>
          </CardHeader>
          <CardContent>
            {result ? (
              <ResultSummary
                result={result}
                patientName={result.patient_id ? names.data?.get(result.patient_id) : undefined}
                missing={score?.missing_actions ?? []}
                extra={score?.extra_actions ?? []}
              />
            ) : (
              <p className="text-sm text-muted-foreground">Not processed in the latest run.</p>
            )}
          </CardContent>
        </Card>
        <Card className="gap-3">
          <CardHeader>
            <CardTitle className="text-base">What the label expects</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {expected ? (
              <>
                <p>
                  <span className="text-muted-foreground">Urgency: </span>
                  {expected.accepted_urgency.join(" or ")}
                </p>
                <p>
                  <span className="text-muted-foreground">Patient: </span>
                  <span className="font-mono">{expected.patient_id ?? "null"}</span>
                </p>
                <ChipList
                  label="Expected actions"
                  items={expected.expected_actions}
                  format={actionLabel}
                />
                {expected.must_not.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-muted-foreground">Must not:</p>
                    <ChipList label="Must not" items={expected.must_not} format={label} />
                  </div>
                )}
                {score && (
                  <ul aria-label="Checks" className="flex flex-wrap gap-1.5 pt-1">
                    {(
                      [
                        ["Urgency", score.urgency_ok],
                        ["Actions", score.actions_exact],
                        ["Patient", score.patient_ok],
                        ["Routing", score.routing_ok],
                        ["Intents", score.intent_f1 === 1],
                      ] as const
                    ).map(([name, ok]) => (
                      <li key={name}>
                        <Badge variant={ok ? "outline" : "destructive"}>
                          {name} {ok ? "ok" : "differs"}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
                {item.root_cause && (
                  <p className="rounded-md border border-warning bg-warning/10 p-2">
                    <span className="font-medium">Root cause: </span>
                    {item.root_cause}
                  </p>
                )}
              </>
            ) : (
              <p className="text-muted-foreground">No label for this message.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {log && (
        <Card className="gap-3">
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center gap-2 text-base">
              Trace
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
                <span className="ml-auto text-xs font-normal text-muted-foreground">
                  {seconds(log.latency_s)}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {log.triage && (
              <p className="text-sm text-muted-foreground">Triage: {log.triage.rationale}</p>
            )}
            <TraceTimeline calls={log.trace ?? []} />
            {log.guard_violations && log.guard_violations.length > 0 && (
              <div className="rounded-md border border-warning bg-warning/10 p-3 text-sm">
                <p className="font-medium">Post-guard corrections</p>
                <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                  {log.guard_violations.map((g) => (
                    <li key={g}>{g}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </article>
  );
}
