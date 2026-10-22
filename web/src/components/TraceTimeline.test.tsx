import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fixtureTrace } from "@/test/fixtures";

import { TraceTimeline } from "./TraceTimeline";

describe("TraceTimeline", () => {
  it("lists calls in order with their outcome", () => {
    render(<TraceTimeline calls={fixtureTrace} />);
    const items = within(screen.getByRole("list", { name: "Tool calls" })).getAllByRole("listitem");
    expect(items).toHaveLength(4);
    expect(items[1]).toHaveTextContent("check_refill_eligibility");
    expect(items[1]).toHaveTextContent("medication_query=lisinopril");
    expect(items[1]).toHaveTextContent("prepare");
  });

  it("never shows the verification token or the reply text in the summary", () => {
    render(
      <TraceTimeline
        calls={[
          {
            name: "list_medications",
            input: { verification_token: "[redacted]" },
            ok: true,
            output: {},
          },
        ]}
      />,
    );
    expect(screen.getByText("list_medications").parentElement).not.toHaveTextContent(
      "verification_token",
    );
  });

  it("marks refused calls and expands to show the reason", async () => {
    render(
      <TraceTimeline
        calls={[
          {
            name: "book_appointment",
            input: { provider: "OKAFOR" },
            ok: false,
            output: { reason: "Dr. Okafor is on leave." },
          },
        ]}
      />,
    );
    expect(screen.getByText("refused")).toBeInTheDocument();
    await userEvent.click(screen.getByText("book_appointment"));
    expect(screen.getByText("Dr. Okafor is on leave.")).toBeVisible();
  });

  it("says when there were no calls", () => {
    render(<TraceTimeline calls={[]} />);
    expect(screen.getByText("No tool calls.")).toBeInTheDocument();
  });
});
