import type { ReactNode } from "react";

import { ChipList } from "@/components/ChipList";
import { ReplyCard } from "@/components/ReplyCard";
import { UrgencyBadge } from "@/components/UrgencyBadge";
import type { AgentResult } from "@/features/inbox/schemas";
import { actionLabel, label, queueLabel } from "@/lib/format";

interface Props {
  result: AgentResult;
  patientName?: string | undefined;
  missing?: string[];
  extra?: string[];
}

function Row({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:gap-4">
      <dt className="shrink-0 text-muted-foreground sm:w-24">{term}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

/** ResultSummary: the output record in the brief's schema, readable at a glance. */
export function ResultSummary({ result, patientName, missing = [], extra = [] }: Props) {
  const emergency = result.actions.includes("escalate_emergency");
  return (
    <div className="space-y-4">
      <dl className="space-y-3 text-sm">
        <Row term="Urgency">
          <UrgencyBadge urgency={result.urgency} />
        </Row>
        <Row term="Patient">
          {result.patient_id ? (
            <span>
              <span className="font-mono">{result.patient_id}</span>
              {patientName && <span className="text-muted-foreground"> · {patientName}</span>}
            </span>
          ) : (
            <span className="text-muted-foreground">Not verified (null)</span>
          )}
        </Row>
        <Row term="Intents">
          <ChipList label="Intents" items={result.intents} format={label} />
        </Row>
        <Row term="Actions">
          <ChipList
            label="Actions"
            items={result.actions}
            format={actionLabel}
            missing={missing}
            extra={extra}
          />
        </Row>
        <Row term="Routed to">
          <ChipList
            label="Queues"
            items={result.routed_to}
            format={queueLabel}
            emptyText="No human queue"
          />
        </Row>
      </dl>
      <ReplyCard text={result.reply_draft} emergency={emergency} />
    </div>
  );
}
