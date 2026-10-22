import type { ReactNode } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Pending, QueryError } from "@/components/QueryState";
import { Segmented } from "@/components/Segmented";
import { StatTile } from "@/components/StatTile";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DatasetId } from "@/features/inbox/schemas";
import { pct, seconds, usd } from "@/lib/format";

import { useEvalReport, useStability } from "../hooks";
import { differs } from "../rootCause";
import { ActionsBelowFull, Differences, Generalisation } from "./EvalInsights";
import { EmergencyList, SafetyList } from "./EvalTables";
import { StabilityCard } from "./StabilityCard";

const DATASETS: { value: DatasetId; label: string }[] = [
  { value: "sample", label: "Sample (40)" },
  { value: "holdout", label: "Held-out (13)" },
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="gap-3">
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/** EvalPage: the measured results, failures first. Every number comes from `make eval`. */
export function EvalPage({
  dataset,
  onDataset,
}: {
  dataset: DatasetId;
  onDataset: (d: DatasetId) => void;
}) {
  const report = useEvalReport(dataset);
  const stability = useStability();

  let body;
  if (report.isPending) body = <Pending label="Loading evaluation" />;
  else if (report.isError)
    body = (
      <QueryError
        error={report.error}
        onRetry={() => void report.refetch()}
        notFound={
          <p>
            No evaluation for this dataset yet. Run{" "}
            <code className="rounded bg-muted px-1">make run && make eval</code>
            {dataset === "holdout" ? " (or make holdout)" : ""}.
          </p>
        }
      />
    );
  else {
    const r = report.data;
    const s = r.scores;
    const wrong = s.per_message.filter(differs);
    // Calls the provider served from a fallback model, so the run line never hides them.
    const others = Object.entries(r.models_served ?? {})
      .filter(([m]) => m !== r.meta.model)
      .map(([m, n]) => `${m} (${String(n)} calls)`);
    body = (
      <div className="space-y-6">
        <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>Run {r.meta.run_id}</span>
          <span>{r.meta.model}</span>
          <span>
            {r.meta.n} messages in {seconds(r.meta.wall_s)}
          </span>
          {others.length > 0 && <span>also served by {others.join(", ")}</span>}
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            emphasis
            label="Emergency recall"
            value={pct(s.emergency.recall)}
            tone={s.emergency.recall === 1 ? "good" : "bad"}
            hint={`${String(s.emergency.n_labelled - s.emergency.missed.length)} of ${String(s.emergency.n_labelled)} escalated`}
          />
          <StatTile
            emphasis
            label="must_not violations"
            value={String(r.must_not_violations.length)}
            tone={r.must_not_violations.length === 0 ? "good" : "bad"}
            hint="Checked on reply, trace and final store"
          />
          <StatTile label="Urgency accuracy" value={pct(s.urgency_accuracy)} />
          <StatTile
            label="Exact action set"
            value={pct(s.actions.exact_match)}
            hint={`Micro F1 ${pct(s.actions.micro.f1)} · macro F1 ${pct(s.actions.macro_f1)}`}
          />
          <StatTile label="Routing accuracy" value={pct(s.routing_accuracy)} />
          <StatTile label="patient_id accuracy" value={pct(s.patient_id_accuracy)} />
          <StatTile label="Intent F1" value={pct(s.intent_f1)} />
          <StatTile
            label="Cost, full run"
            value={usd(r.cost.total_usd)}
            hint={`${usd(r.cost.mean_usd_per_message)}/message · p50 ${seconds(r.latency.p50_s)} · p95 ${seconds(r.latency.p95_s)}`}
          />
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <Section title="Emergencies">
            <EmergencyList report={r} />
          </Section>
          <Section title="must_not violations">
            <SafetyList
              title="must_not violations"
              okText="None. Every must_not tag in the labels was checked against the reply, the tool trace and the final store."
              rows={r.must_not_violations.map((v) => ({
                id: v.id,
                what: v.tag,
                evidence: v.evidence,
              }))}
            />
          </Section>
          <Section title="Global safety checks (every message)">
            <SafetyList
              title="Global safety findings"
              okText="None: no invalid bookings, approvals, non-template emergency replies, advice keywords or PHI to unverified senders."
              rows={r.global_safety.map((g) => ({ id: g.id, what: g.check, evidence: g.evidence }))}
            />
          </Section>
        </div>
        {stability.isSuccess && (
          <Section title="Stability across repeated runs">
            <StabilityCard stability={stability.data} model={r.meta.model} />
          </Section>
        )}
        <Section title={`Where the ${String(wrong.length)} differences from the label come from`}>
          <Differences report={r} dataset={dataset} />
        </Section>
        <div className="grid gap-4 lg:grid-cols-3">
          <Section title="Generalisation: sample and held-out">
            <Generalisation />
          </Section>
          <Section title="Actions below 100%">
            <ActionsBelowFull perAction={s.actions.per_action} />
          </Section>
          <Section title="Post-guard interventions">
            {Object.keys(r.guard_interventions).length === 0 ? (
              <p className="text-sm text-muted-foreground">
                The guard did not need to change any result.
              </p>
            ) : (
              <ul className="space-y-2 text-sm">
                {Object.entries(r.guard_interventions).map(([id, v]) => (
                  <li key={id}>
                    <span className="font-mono font-medium">{id}</span>:{" "}
                    <span className="text-muted-foreground">{v.join("; ")}</span>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Evaluation"
        description="Measured on the labelled set. Failures are listed, not hidden."
      >
        <Segmented label="Dataset" value={dataset} onChange={onDataset} options={DATASETS} />
      </PageHeader>
      {body}
    </div>
  );
}
