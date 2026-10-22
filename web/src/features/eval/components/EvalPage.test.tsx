import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderRoute } from "@/test/app";
import { fixtureEval } from "@/test/fixtures";
import { server } from "@/test/msw";

describe("EvalPage", () => {
  it("leads with emergency recall and must_not violations", async () => {
    renderRoute("/eval");
    const tile = (await screen.findByText("Emergency recall")).parentElement;
    expect(tile).toHaveTextContent("100.0%");
    expect(tile).toHaveTextContent("5 of 5 escalated");
    expect(screen.getByText(/No missed emergencies \(5 of 5 escalated\)/)).toBeInTheDocument();
    expect(screen.getByText(/None. Every must_not tag/)).toBeInTheDocument();
    expect(
      screen.getByText(/served by nvidia\/nemotron-3-ultra-550b-a55b:free \(180 calls\)/),
    ).toBeInTheDocument();
  });

  it("lists wrong cases with root causes and links to the inbox", async () => {
    renderRoute("/eval");
    const link = await screen.findByRole("link", { name: "M004" });
    expect(link).toHaveAttribute("href", expect.stringContaining("/inbox"));
    expect(
      screen.getByText("Policy says route to provider; the label omits it."),
    ).toBeInTheDocument();
    await userEvent.click(link);
    expect(await screen.findByRole("heading", { name: "Inbox" })).toBeInTheDocument();
  });

  it("shows violations and missed emergencies plainly", async () => {
    const bad = fixtureEval();
    bad.scores.emergency = {
      n_labelled: 5,
      recall: 0.8,
      precision: 1,
      missed: ["M017"],
      over_escalated: ["M024"],
    };
    bad.must_not_violations = [
      { id: "M005", tag: "prepare_refill_for_approval", evidence: "a refill request was prepared" },
    ];
    server.use(http.get("*/api/datasets/:name/eval", () => HttpResponse.json(bad)));
    renderRoute("/eval");
    expect(await screen.findByText("Missed emergencies: M017")).toBeInTheDocument();
    expect(screen.getByText(/Over-escalated \(not labelled emergency\): M024/)).toBeInTheDocument();
    expect(screen.getByText("a refill request was prepared")).toBeInTheDocument();
  });

  it("shows stability when measured", async () => {
    server.use(
      http.get("*/api/stability", () =>
        HttpResponse.json({
          runs: 3,
          messages: 40,
          changed: 2,
          changed_ids: ["M025", "M034"],
          emergency_flips: [],
        }),
      ),
    );
    renderRoute("/eval");
    expect(await screen.findByText(/changed outcome across 3 runs/)).toBeInTheDocument();
  });

  it("explains how to create a missing evaluation", async () => {
    renderRoute("/eval?dataset=holdout");
    expect(await screen.findByText("Nothing here yet")).toBeInTheDocument();
  });
});
