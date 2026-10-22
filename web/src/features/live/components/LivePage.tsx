import { KeyRound, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useHealth, useInbox } from "@/features/inbox/hooks";
import type { DatasetId } from "@/features/inbox/schemas";
import { useResetLiveState } from "@/features/state/hooks";

import type { ComposeValues } from "../schemas";
import { useLiveRun } from "../useLiveRun";
import { ComposeForm } from "./ComposeForm";
import { RunView } from "./RunView";

/** LivePage: process an unseen message end to end and watch every stage. */
export function LivePage({ replay }: { replay?: { id: string; dataset: DatasetId } | undefined }) {
  const { run, start } = useLiveRun();
  const inbox = useInbox(replay?.dataset ?? "sample");
  const replayed = replay
    ? inbox.data?.items.find((i) => i.message.id === replay.id)?.message
    : undefined;
  const initial: ComposeValues | undefined = replayed && {
    from_name: replayed.from_name,
    from_contact: replayed.from_contact,
    channel:
      replayed.channel === "portal" || replayed.channel === "email" ? replayed.channel : "sms",
    body: replayed.body,
    stated_dob: replayed.stated_dob ?? "",
  };
  const health = useHealth();
  const reset = useResetLiveState();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Live console"
        description="Send a new message through the real agent: safety pre-screen, verification, triage, MCP tools, post-guard."
      >
        <Button
          variant="outline"
          size="sm"
          disabled={reset.isPending || run.status === "running"}
          onClick={() => {
            reset.mutate(undefined, {
              onSuccess: () => toast.success("Live clinic data reset to the JSON files"),
              onError: () => toast.error("Could not reset the live data"),
            });
          }}
        >
          <RotateCcw aria-hidden />
          Reset live data
        </Button>
      </PageHeader>
      {health.data && !health.data.llm_configured && (
        <Alert>
          <KeyRound aria-hidden />
          <AlertTitle>No LLM API key configured</AlertTitle>
          <AlertDescription>
            Emergencies are still escalated by the deterministic pre-screen. Every other message
            falls back safely to a human queue. Add OPENROUTER_API_KEY (free models) or
            ANTHROPIC_API_KEY to .env to run the full agent.
          </AlertDescription>
        </Alert>
      )}
      <div className="grid gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-2">
          <CardContent>
            {replayed && (
              <p role="status" className="mb-4 rounded-md bg-accent/50 p-2 text-xs">
                Re-running <span className="font-mono">{replayed.id}</span> from the{" "}
                {replay?.dataset === "holdout" ? "held-out" : "sample"} run. Press Process message;
                the result goes to the live session, not the graded run.
              </p>
            )}
            <ComposeForm
              key={replayed?.id ?? "new"}
              initial={initial}
              running={run.status === "running"}
              onSubmit={(payload) => void start(payload)}
            />
          </CardContent>
        </Card>
        <section aria-label="Run" className="xl:col-span-3">
          <RunView run={run} />
        </section>
      </div>
    </div>
  );
}
