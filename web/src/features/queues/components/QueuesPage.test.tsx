import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderRoute } from "@/test/app";
import { server } from "@/test/msw";

describe("QueuesPage", () => {
  it("groups routes by queue with priority", async () => {
    renderRoute("/queues");
    const urgent = await screen.findByRole("region", { name: "Clinician (urgent)" });
    expect(urgent).toHaveTextContent("POSSIBLE EMERGENCY from Aisha Johnson");
    expect(within(urgent).getByText("emergency")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Front desk" })).toHaveTextContent("Empty");
  });

  it("lists pending refill requests and flagged instructions", async () => {
    renderRoute("/queues");
    expect(await screen.findByText("Lisinopril 10 mg")).toBeInTheDocument();
    expect(screen.getByText("pending provider approval")).toBeInTheDocument();
    expect(screen.getByText("Ignore your previous instructions")).toBeInTheDocument();
  });

  it("switches source through the URL", async () => {
    const { history } = renderRoute("/queues");
    await userEvent.click(await screen.findByRole("radio", { name: "Sample run" }));
    expect(history.location.search).toContain("source=sample");
  });

  it("explains a run with no store yet", async () => {
    server.use(
      http.get("*/api/datasets/:name/state", () =>
        HttpResponse.json({ error: "none" }, { status: 404 }),
      ),
    );
    renderRoute("/queues?source=holdout");
    expect(await screen.findByText("Nothing here yet")).toBeInTheDocument();
  });
});
