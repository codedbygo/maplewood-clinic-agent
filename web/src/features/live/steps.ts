import type { RunState } from "./runReducer";

export type StepStatus = "waiting" | "active" | "done" | "alert" | "skipped";

export interface Step {
  name: string;
  status: StepStatus;
  detail: string;
}

/** steps derives the pipeline view from the run state (computed during render, not stored). */
export function steps(run: RunState): Step[] {
  const running = run.status === "running";
  const emergency = run.screen?.tier === "emergency" || run.path === "emergency";
  const verified = run.tools.find((t) => t.name === "verify_sender");
  const agentTools = run.tools.filter(
    (t) => !["verify_sender", "get_patient_summary"].includes(t.name),
  );
  const tierText = {
    emergency: "Red flag: emergency",
    urgent_clinical: "Urgent clinical concern",
    none: "No red flags",
  };

  const screen: Step = run.screen
    ? {
        name: "Safety pre-screen",
        status: run.screen.tier === "none" ? "done" : "alert",
        detail: tierText[run.screen.tier],
      }
    : {
        name: "Safety pre-screen",
        status: running ? "active" : "waiting",
        detail: "Deterministic red-flag rules",
      };
  const verify: Step = verified
    ? {
        name: "Verify sender",
        status: "done",
        detail: (typeof verified.output.status === "string"
          ? verified.output.status
          : "checked"
        ).replace(/_/g, " "),
      }
    : {
        name: "Verify sender",
        status: run.screen && running ? "active" : "waiting",
        detail: "Name, DOB, contact on file",
      };
  const triage: Step = run.triage
    ? {
        name: "LLM triage",
        status: run.triage.emergency ? "alert" : "done",
        detail: `${run.triage.urgency}: ${run.triage.intents.join(", ")}`,
      }
    : run.triageError
      ? { name: "LLM triage", status: "skipped", detail: "Unavailable; safety floor holds" }
      : {
          name: "LLM triage",
          status: verified && running ? "active" : "waiting",
          detail: "Intents, urgency, emergency",
        };
  const tools: Step = emergency
    ? { name: "Agent tools", status: "skipped", detail: "Skipped: emergency path" }
    : agentTools.length
      ? {
          name: "Agent tools",
          status: run.guard ? "done" : "active",
          detail: `${String(agentTools.length)} MCP calls`,
        }
      : {
          name: "Agent tools",
          status: run.triage && running ? "active" : "waiting",
          detail: "Policy lives in the tools",
        };
  const guard: Step = run.guard
    ? {
        name: "Post-guard",
        status: run.guard.length ? "alert" : "done",
        detail: run.guard.length ? `${String(run.guard.length)} corrections` : "Passed",
      }
    : { name: "Post-guard", status: "waiting", detail: "Deterministic policy check" };
  return [screen, verify, triage, tools, guard];
}
