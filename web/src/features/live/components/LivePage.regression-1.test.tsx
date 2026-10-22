// Regression: CR-8 (code review 2026-10-22) — a stream that ended without a result left the run "running"
// forever with the submit button disabled; a malformed result was dropped silently.
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderRoute } from "@/test/app";
import { fixtureScreen } from "@/test/fixtures";
import { server, sseBody } from "@/test/msw";

async function runExample() {
  renderRoute("/");
  await userEvent.click(await screen.findByRole("button", { name: "Routine refill" }));
  await userEvent.click(screen.getByRole("button", { name: "Process message" }));
}

describe("LivePage stream endings", () => {
  it("fails the run when the stream ends without a result", async () => {
    server.use(
      http.post(
        "*/api/live/process",
        () =>
          new HttpResponse(
            sseBody([{ type: "stage", stage: "prescreen", data: fixtureScreen("none") }]),
          ),
      ),
    );
    await runExample();
    expect(await screen.findByText(/ended before a result/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Process message" })).toBeEnabled();
  });

  it("fails the run when the result cannot be read", async () => {
    server.use(
      http.post(
        "*/api/live/process",
        () => new HttpResponse(sseBody([{ type: "result", data: { id: 1 } }])),
      ),
    );
    await runExample();
    expect(await screen.findByText(/could not be read/)).toBeInTheDocument();
  });
});
