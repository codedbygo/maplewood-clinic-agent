import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderRoute } from "@/test/app";
import { fixtureResult, fixtureScreen } from "@/test/fixtures";
import { server, sseBody } from "@/test/msw";

describe("LivePage", () => {
  it("validates the form before sending", async () => {
    renderRoute("/");
    await userEvent.click(await screen.findByRole("button", { name: "Process message" }));
    expect(screen.getByText("Sender name is required")).toBeInTheDocument();
    expect(screen.getByLabelText("Sender name")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Message text is required")).toBeInTheDocument();
  });

  it("rejects a badly formatted date of birth", async () => {
    renderRoute("/");
    await userEvent.click(await screen.findByRole("button", { name: "Routine refill" }));
    await userEvent.type(screen.getByLabelText("Stated date of birth (optional)"), "02/11/1971");
    await userEvent.click(screen.getByRole("button", { name: "Process message" }));
    expect(screen.getByText("Use YYYY-MM-DD")).toBeInTheDocument();
  });

  it("streams a run: pipeline, tool calls and result", async () => {
    renderRoute("/");
    await userEvent.click(await screen.findByRole("button", { name: "Routine refill" }));
    expect(screen.getByLabelText("Sender name")).toHaveValue("Robert Chen");
    await userEvent.click(screen.getByRole("button", { name: "Process message" }));

    expect(await screen.findByText(/LIVE-1 processed in 4.2s/)).toBeInTheDocument();
    const pipeline = screen.getByRole("list", { name: "Pipeline" });
    expect(within(pipeline).getByText("No red flags")).toBeInTheDocument();
    expect(within(pipeline).getByText("verified patient")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Tool calls" })).toHaveTextContent(
      "check_refill_eligibility",
    );
    expect(screen.getByRole("list", { name: "Actions" })).toHaveTextContent(
      "Prepare refill for approval",
    );
    expect(screen.getByText(/Hi Robert, your lisinopril refill/)).toBeInTheDocument();
  });

  it("shows the emergency banner and skips the agent tools on an emergency", async () => {
    server.use(
      http.post(
        "*/api/live/process",
        () =>
          new HttpResponse(
            sseBody([
              {
                type: "stage",
                stage: "prescreen",
                data: fixtureScreen("emergency", ["chest_pain"]),
              },
              { type: "stage", stage: "path", data: { path: "emergency", error: null } },
              { type: "guard", data: { violations: [], extra_routes: [] } },
              {
                type: "result",
                data: fixtureResult({
                  id: "LIVE-2",
                  urgency: "emergency",
                  actions: ["escalate_emergency"],
                  routed_to: ["clinician_urgent"],
                  reply_draft: "Please call 911 now.",
                }),
                latency_s: 0.3,
                llm_calls: [],
              },
            ]),
          ),
      ),
    );
    renderRoute("/");
    await userEvent.click(
      await screen.findByRole("button", { name: "Downplayed cardiac symptoms" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Process message" }));
    expect(await screen.findByText("Emergency escalated")).toBeInTheDocument();
    expect(screen.getByText("Skipped: emergency path")).toBeInTheDocument();
    expect(screen.getByText("chest_pain")).toBeInTheDocument();
  });

  it("shows a triage failure as degraded, not broken", async () => {
    server.use(
      http.post(
        "*/api/live/process",
        () =>
          new HttpResponse(
            sseBody([
              { type: "stage", stage: "triage", data: null, error: "no API key" },
              { type: "error", error: "tool loop failed" },
            ]),
          ),
      ),
    );
    renderRoute("/");
    await userEvent.click(await screen.findByRole("button", { name: "Routine refill" }));
    await userEvent.click(screen.getByRole("button", { name: "Process message" }));
    expect(await screen.findByText("Run failed")).toBeInTheDocument();
    expect(screen.getByText("Unavailable; safety floor holds")).toBeInTheDocument();
  });

  it("explains a server rejection", async () => {
    server.use(
      http.post("*/api/live/process", () =>
        HttpResponse.json({ error: "invalid" }, { status: 422 }),
      ),
    );
    renderRoute("/");
    await userEvent.click(await screen.findByRole("button", { name: "Routine refill" }));
    await userEvent.click(screen.getByRole("button", { name: "Process message" }));
    expect(
      await screen.findByText("The server rejected the message. Check the fields."),
    ).toBeInTheDocument();
  });

  it("warns when no API key is configured and resets live data", async () => {
    server.use(
      http.get("*/api/health", () =>
        HttpResponse.json({ ok: true, model: null, llm_configured: false }),
      ),
    );
    renderRoute("/");
    expect(await screen.findByText("No LLM API key configured")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reset live data" }));
    expect(await screen.findByText("Live clinic data reset to the JSON files")).toBeInTheDocument();
  });
});
