import { CheckCircle2, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { actionLabel, label, pct } from "@/lib/format";

import type { EvalReport } from "../schemas";

export function SafetyList({
  title,
  rows,
  okText,
}: {
  title: string;
  rows: { id: string; what: string; evidence: string }[];
  okText: string;
}) {
  if (rows.length === 0) {
    return (
      <p className="flex items-center gap-2 rounded-md border border-success/40 bg-success/10 p-3 text-sm">
        <ShieldCheck aria-hidden className="size-4 text-success" />
        {okText}
      </p>
    );
  }
  return (
    <Table aria-label={title}>
      <TableHeader>
        <TableRow>
          <TableHead>Message</TableHead>
          <TableHead>Check</TableHead>
          <TableHead>Evidence</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r, i) => (
          <TableRow key={`${r.id}-${r.what}-${String(i)}`}>
            <TableCell className="font-mono">{r.id}</TableCell>
            <TableCell>
              <Badge variant="destructive">{label(r.what)}</Badge>
            </TableCell>
            <TableCell className="whitespace-normal">{r.evidence}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function PerActionTable({
  perAction,
}: {
  perAction: EvalReport["scores"]["actions"]["per_action"];
}) {
  const rows = Object.entries(perAction).sort(([, a], [, b]) => b.tp + b.fn - (a.tp + a.fn));
  return (
    <Table aria-label="Per-action results">
      <TableHeader>
        <TableRow>
          <TableHead>Action</TableHead>
          <TableHead className="w-1/3">Recall</TableHead>
          <TableHead>Precision</TableHead>
          <TableHead className="text-right">Expected</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map(([action, v]) => (
          <TableRow key={action}>
            <TableCell>{actionLabel(action)}</TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <Progress
                  value={v.recall * 100}
                  aria-label={`${actionLabel(action)} recall`}
                  className="h-2"
                />
                <span className="w-14 text-right text-xs tabular-nums">
                  {v.tp + v.fn ? pct(v.recall) : "n/a"}
                </span>
              </div>
            </TableCell>
            <TableCell className="tabular-nums">{v.tp + v.fp ? pct(v.precision) : "n/a"}</TableCell>
            <TableCell className="text-right tabular-nums">{v.tp + v.fn}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function EmergencyList({ report }: { report: EvalReport }) {
  const em = report.scores.emergency;
  return (
    <div className="space-y-2 text-sm">
      {em.missed.length === 0 ? (
        <p className="flex items-center gap-2 font-medium text-success">
          <CheckCircle2 aria-hidden className="size-4" /> No missed emergencies ({em.n_labelled} of{" "}
          {em.n_labelled} escalated).
        </p>
      ) : (
        <p className="font-medium text-destructive">Missed emergencies: {em.missed.join(", ")}</p>
      )}
      <p className="text-muted-foreground">
        Over-escalated (not labelled emergency):{" "}
        {em.over_escalated.length ? em.over_escalated.join(", ") : "none"}
      </p>
    </div>
  );
}
