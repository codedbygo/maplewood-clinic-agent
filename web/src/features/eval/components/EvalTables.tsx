import { CheckCircle2, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { label } from "@/lib/format";

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
