import { AlertCircle, Siren, Sparkles } from "lucide-react";

import { Empty } from "@/components/QueryState";
import { ResultSummary } from "@/components/ResultSummary";
import { TraceTimeline } from "@/components/TraceTimeline";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePatientNames } from "@/features/state/hooks";
import { label, seconds } from "@/lib/format";

import type { RunState } from "../runReducer";
import { PipelineSteps } from "./PipelineSteps";

/** RunView shows one live run: pipeline, safety and triage findings, tool calls and the result. */
export function RunView({ run }: { run: RunState }) {
  const names = usePatientNames();
  if (run.status === "idle") {
    return (
      <Empty title="No message processed yet">
        Pick an example or write a new message, then press Process. Every stage streams here as it
        happens.
      </Empty>
    );
  }
  const escalated = run.result?.actions.includes("escalate_emergency") ?? false;
  return (
    <div className="space-y-4" aria-busy={run.status === "running"}>
      {escalated && (
        <Alert variant="destructive" className="border-destructive bg-destructive/10">
          <Siren aria-hidden />
          <AlertTitle>Emergency escalated</AlertTitle>
          <AlertDescription>
            Routed to the urgent clinician queue. The sender was only told to call 911 or go to the
            nearest emergency department; no clinical work was done.
          </AlertDescription>
        </Alert>
      )}
      {run.status === "error" && (
        <Alert variant="destructive">
          <AlertCircle aria-hidden />
          <AlertTitle>Run failed</AlertTitle>
          <AlertDescription>{run.error}</AlertDescription>
        </Alert>
      )}
      <PipelineSteps run={run} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="gap-3">
          <CardHeader>
            <CardTitle className="text-base">Safety pre-screen and triage</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {run.screen && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted-foreground">Rules:</span>
                <Badge variant={run.screen.tier === "none" ? "outline" : "destructive"}>
                  {label(run.screen.tier)}
                </Badge>
                {run.screen.matches.map((m) => (
                  <Badge key={m} variant="outline" className="font-mono font-normal">
                    {m}
                  </Badge>
                ))}
              </div>
            )}
            {run.triage && (
              <div className="space-y-1">
                <p className="flex items-center gap-1.5">
                  <Sparkles aria-hidden className="size-4 text-primary" />
                  <span className="font-medium">LLM triage:</span> {run.triage.urgency}
                  {run.triage.suspicious_instruction && (
                    <Badge variant="destructive">Suspicious instruction</Badge>
                  )}
                </p>
                <p className="text-muted-foreground">{run.triage.rationale}</p>
              </div>
            )}
            {run.triageError && (
              <p className="text-muted-foreground">LLM triage unavailable: {run.triageError}</p>
            )}
          </CardContent>
        </Card>
        <Card className="gap-3">
          <CardHeader>
            <CardTitle className="text-base">Result</CardTitle>
          </CardHeader>
          <CardContent>
            {run.result ? (
              <>
                <ResultSummary
                  result={run.result}
                  patientName={
                    run.result.patient_id ? names.data?.get(run.result.patient_id) : undefined
                  }
                />
                {run.latency !== undefined && (
                  <p className="mt-3 text-xs text-muted-foreground">
                    {run.result.id} processed in {seconds(run.latency)}
                  </p>
                )}
              </>
            ) : (
              <p role="status" className="text-sm text-muted-foreground">
                {run.status === "running" ? "Working" : "No result"}
              </p>
            )}
          </CardContent>
        </Card>
      </div>
      <Card className="gap-3">
        <CardHeader>
          <CardTitle className="text-base">MCP tool calls ({run.tools.length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <TraceTimeline calls={run.tools} live />
          {run.guard && run.guard.length > 0 && (
            <div className="rounded-md border border-warning bg-warning/10 p-3 text-sm">
              <p className="font-medium">Post-guard corrected the result</p>
              <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                {run.guard.map((g) => (
                  <li key={g}>{g}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
