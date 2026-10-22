// Regression: ISSUE-010 — stability measured without any LLM was shown as if it measured the current model.
// Found by /qa on 2026-10-22
// Report: .gstack/qa-reports/qa-report-localhost-2026-10-22.md
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderRoute } from "@/test/app";
import { server } from "@/test/msw";

const base = { runs: 3, messages: 40, changed: 0, changed_ids: [], emergency_flips: [] };

describe("EvalPage stability provenance", () => {
  it("names the model that stability measured when it matches the run", async () => {
    server.use(
      http.get("*/api/stability", () =>
        HttpResponse.json({ ...base, model: "claude-sonnet-5-5", complete: true }),
      ),
    );
    renderRoute("/eval");
    expect(await screen.findByText(/Measured with claude-sonnet-5-5/)).toBeInTheDocument();
    expect(screen.queryByText(/does not describe this run/)).not.toBeInTheDocument();
  });

  it("warns when stability came from a different model", async () => {
    server.use(
      http.get("*/api/stability", () =>
        HttpResponse.json({ ...base, model: "other/model:free", complete: true }),
      ),
    );
    renderRoute("/eval");
    expect(await screen.findByText(/does not describe this run/)).toBeInTheDocument();
  });

  it("warns when the stability file does not say what it measured", async () => {
    server.use(http.get("*/api/stability", () => HttpResponse.json(base)));
    renderRoute("/eval");
    expect(await screen.findByText(/does not describe this run/)).toBeInTheDocument();
  });

  it("warns when a stability run stopped early", async () => {
    server.use(
      http.get("*/api/stability", () =>
        HttpResponse.json({ ...base, model: "claude-sonnet-5-5", complete: false }),
      ),
    );
    renderRoute("/eval");
    expect(await screen.findByText(/at least one run stopped early/)).toBeInTheDocument();
  });
});
