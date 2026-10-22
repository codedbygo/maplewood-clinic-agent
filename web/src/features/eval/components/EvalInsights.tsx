import { Link } from "@tanstack/react-router";
import { CheckCircle2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import type { DatasetId } from "@/features/inbox/schemas";
import { actionLabel, pct } from "@/lib/format";
import { cn } from "@/lib/utils";

import { useEvalReport } from "../hooks";
import { CATEGORIES, differs, splitRootCause, type Category } from "../rootCause";
import type { EvalReport } from "../schemas";

type PerMessage = EvalReport["scores"]["per_message"][number];

const SWATCH: Record<Category, string> = {
  "Accepted over-escalation": "bg-destructive",
  "Guard bug (fixed)": "bg-chart-4",
  Judgement: "bg-chart-1",
  "Model variance": "bg-muted-foreground",
  "By design": "bg-chart-2",
  "Intents only": "bg-chart-3",
  Other: "bg-chart-5",
  "Not analysed": "bg-muted",
};

function WhatDiffers({ m }: { m: PerMessage }) {
  const parts = [
    !m.urgency_ok && "urgency",
    !m.patient_ok && "patient_id",
    !m.routing_ok && "routing",
    m.intent_f1 !== 1 && "intents",
    ...m.missing_actions.map((a) => `missing ${actionLabel(a)}`),
    ...m.extra_actions.map((a) => `extra ${actionLabel(a)}`),
  ].filter((p): p is string => Boolean(p));
  return (
    <ul className="flex flex-wrap gap-1">
      {parts.map((p) => (
        <li key={p}>
          <Badge variant="outline" className="font-normal">
            {p}
          </Badge>
        </li>
      ))}
    </ul>
  );
}

/** Differences: every case that differs from the label, grouped by root cause, filterable by group. */
export function Differences({ report, dataset }: { report: EvalReport; dataset: DatasetId }) {
  const [only, setOnly] = useState<Category | null>(null);
  const rows = report.scores.per_message
    .filter(differs)
    .map((m) => ({ m, ...splitRootCause(report.root_causes[m.id]) }));
  if (rows.length === 0)
    return (
      <p className="flex items-center gap-2 text-sm text-success">
        <CheckCircle2 aria-hidden className="size-4" /> Every message matches its label.
      </p>
    );

  const groups = CATEGORIES.map((c) => ({
    c,
    n: rows.filter((r) => r.category === c).length,
  })).filter((g) => g.n > 0);
  const shown = only ? rows.filter((r) => r.category === only) : rows;

  return (
    <div className="space-y-4">
      <div aria-hidden className="flex h-3 overflow-hidden rounded-full bg-muted">
        {groups.map((g) => (
          <span
            key={g.c}
            className={cn(SWATCH[g.c], only && only !== g.c && "opacity-30")}
            style={{ width: `${String((g.n / rows.length) * 100)}%` }}
          />
        ))}
      </div>
      <div role="group" aria-label="Filter by root cause" className="flex flex-wrap gap-1.5">
        <button
          type="button"
          aria-pressed={only === null}
          onClick={() => {
            setOnly(null);
          }}
          className="rounded-full border px-3 py-1 text-xs hover:bg-accent aria-pressed:bg-accent aria-pressed:font-medium"
        >
          All {rows.length}
        </button>
        {groups.map((g) => (
          <button
            key={g.c}
            type="button"
            aria-pressed={only === g.c}
            onClick={() => {
              setOnly(only === g.c ? null : g.c);
            }}
            className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs hover:bg-accent aria-pressed:bg-accent aria-pressed:font-medium"
          >
            <span aria-hidden className={cn("size-2 rounded-full", SWATCH[g.c])} />
            {g.c} {g.n}
          </button>
        ))}
      </div>
      <ul aria-label="Cases that differ" className="divide-y text-sm">
        {shown.map(({ m, category, detail }) => (
          <li key={m.id} className="grid gap-1 py-2.5 md:grid-cols-12 md:gap-3">
            <div className="flex items-center gap-2 md:col-span-3">
              <Link
                to="/inbox/$messageId"
                params={{ messageId: m.id }}
                search={{ dataset, filter: "all" }}
                className="font-mono font-medium text-primary hover:underline"
              >
                {m.id}
              </Link>
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span aria-hidden className={cn("size-2 rounded-full", SWATCH[category])} />
                {category}
              </span>
            </div>
            <div className="md:col-span-3">
              <WhatDiffers m={m} />
            </div>
            <p className="text-muted-foreground md:col-span-6">{detail}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** ActionsBelowFull: the actions that missed, then the rest in one line. */
export function ActionsBelowFull({
  perAction,
}: {
  perAction: EvalReport["scores"]["actions"]["per_action"];
}) {
  const all = Object.entries(perAction).filter(([, v]) => v.tp + v.fn + v.fp > 0);
  const below = all
    .filter(([, v]) => v.fn > 0 || v.fp > 0)
    .sort(([, a], [, b]) => b.fn + b.fp - (a.fn + a.fp));
  const full = all.filter(([, v]) => v.fn === 0 && v.fp === 0);
  return (
    <div className="space-y-3 text-sm">
      {below.length === 0 ? (
        <p className="text-success">Every action at 100% recall and precision.</p>
      ) : (
        <table aria-label="Actions below 100%" className="w-full">
          <thead className="text-left text-xs text-muted-foreground">
            <tr>
              <th className="pb-2 font-medium">Action</th>
              <th className="pb-2 text-right font-medium">Recall</th>
              <th className="pb-2 text-right font-medium">Precision</th>
              <th className="pb-2 text-right font-medium">Missed</th>
              <th className="pb-2 text-right font-medium">Extra</th>
            </tr>
          </thead>
          <tbody className="divide-y tabular-nums">
            {below.map(([a, v]) => (
              <tr key={a}>
                <td className="py-1.5">{actionLabel(a)}</td>
                <td className="py-1.5 text-right">{v.tp + v.fn ? pct(v.recall) : "n/a"}</td>
                <td className="py-1.5 text-right">{v.tp + v.fp ? pct(v.precision) : "n/a"}</td>
                <td className="py-1.5 text-right">{v.fn}</td>
                <td className="py-1.5 text-right">{v.fp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {full.length > 0 && (
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">{full.length} actions at 100%:</span>{" "}
          {full.map(([a]) => actionLabel(a)).join(", ")}.
        </p>
      )}
    </div>
  );
}

const GENERAL_ROWS: { label: string; get: (r: EvalReport) => string; safety?: boolean }[] = [
  { label: "Emergency recall", get: (r) => pct(r.scores.emergency.recall), safety: true },
  { label: "must_not violations", get: (r) => String(r.must_not_violations.length), safety: true },
  { label: "Urgency accuracy", get: (r) => pct(r.scores.urgency_accuracy) },
  { label: "Routing accuracy", get: (r) => pct(r.scores.routing_accuracy) },
  { label: "patient_id accuracy", get: (r) => pct(r.scores.patient_id_accuracy) },
  { label: "Exact action set", get: (r) => pct(r.scores.actions.exact_match) },
];

/** Generalisation: the sample beside the held-out set, written before the first run and never tuned on. */
export function Generalisation() {
  const sample = useEvalReport("sample");
  const holdout = useEvalReport("holdout");
  if (!sample.data || !holdout.data)
    return (
      <p className="text-sm text-muted-foreground">
        Needs both runs: <code className="rounded bg-muted px-1">make eval</code> and{" "}
        <code className="rounded bg-muted px-1">make holdout</code>.
      </p>
    );
  const s = sample.data;
  const h = holdout.data;
  return (
    <div className="space-y-3 text-sm">
      <table aria-label="Sample and held-out" className="w-full">
        <thead className="text-left text-xs text-muted-foreground">
          <tr>
            <th className="pb-2 font-medium">Metric</th>
            <th className="pb-2 text-right font-medium">Sample ({s.meta.n})</th>
            <th className="pb-2 text-right font-medium">Held-out ({h.meta.n})</th>
          </tr>
        </thead>
        <tbody className="divide-y tabular-nums">
          {GENERAL_ROWS.map((row) => (
            <tr key={row.label} className={cn(row.safety && "font-medium")}>
              <td className="py-1.5">{row.label}</td>
              <td className="py-1.5 text-right">{row.get(s)}</td>
              <td className="py-1.5 text-right">{row.get(h)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-muted-foreground">
        The held-out messages (new emergency phrasings, Spanish, a new injection, holidays) were
        written before the first model run and never used to choose a change.
      </p>
    </div>
  );
}
