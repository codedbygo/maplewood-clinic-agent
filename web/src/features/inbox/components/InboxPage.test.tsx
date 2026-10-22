import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderRoute } from "@/test/app";
import { server } from "@/test/msw";

describe("InboxPage", () => {
  it("lists every message as a row that opens its own page", async () => {
    const { history } = renderRoute("/inbox");
    const list = await screen.findByRole("list", { name: "Messages" });
    expect(within(list).getAllByRole("link")).toHaveLength(3);
    expect(screen.getByText(/Run 20261022T100000Z/)).toBeInTheDocument();
    await userEvent.click(within(list).getAllByRole("link")[0]!);
    expect(history.location.pathname).toBe("/inbox/M001");
    expect(await screen.findByRole("heading", { name: "Robert Chen" })).toBeInTheDocument();
  });

  it("marks emergencies and verdicts in the list", async () => {
    renderRoute("/inbox");
    const list = await screen.findByRole("list", { name: "Messages" });
    expect(within(list).getByText("emergency")).toBeInTheDocument();
    expect(within(list).getAllByText("Matches label")).toHaveLength(2);
    expect(within(list).getByText("differs")).toBeInTheDocument();
  });

  it("filters to messages that differ from the label", async () => {
    const { history } = renderRoute("/inbox");
    await userEvent.click(await screen.findByRole("radio", { name: "Differs from label (1)" }));
    const list = screen.getByRole("list", { name: "Messages" });
    expect(within(list).getAllByRole("link")).toHaveLength(1);
    expect(history.location.search).toContain("filter=attention");
  });

  it("falls back to defaults for bad search params", async () => {
    renderRoute("/inbox?dataset=nope&filter=zzz");
    expect(await screen.findByRole("radio", { name: "All (3)" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("explains how to create a run when there is none", async () => {
    renderRoute("/inbox?dataset=holdout");
    expect(await screen.findByText("No run for this dataset yet")).toBeInTheDocument();
  });

  it("shows an error with retry", async () => {
    server.use(
      http.get("*/api/datasets/:name/inbox", () => HttpResponse.json({}, { status: 500 })),
    );
    renderRoute("/inbox");
    expect(await screen.findByText("Could not load this view")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

describe("MessagePage", () => {
  it("opens an old ?id= link on the message page", async () => {
    const { history } = renderRoute("/inbox?id=M003");
    expect(
      await screen.findByText(/crushing chest pain/, { selector: "blockquote" }),
    ).toBeInTheDocument();
    expect(history.location.pathname).toBe("/inbox/M003");
  });

  it("shows the emergency trace behind its tab", async () => {
    renderRoute("/inbox/M003");
    await userEvent.click(await screen.findByRole("tab", { name: /Trace/ }));
    expect(await screen.findByText("emergency path")).toBeInTheDocument();
  });

  it("explains a difference with the root cause and marks the field", async () => {
    renderRoute("/inbox/M004");
    expect(await screen.findByText(/Policy says route to provider/)).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Agent and label" });
    const routing = within(table).getByRole("rowheader", { name: "Routed to" }).closest("tr")!;
    expect(within(routing).getByLabelText("Differs")).toBeInTheDocument();
  });

  it("steps through the list it came from and back to the inbox", async () => {
    const { history } = renderRoute("/inbox/M001");
    expect(await screen.findByText("1 of 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous message" })).toBeDisabled();
    await userEvent.click(screen.getByRole("link", { name: "Next message: M003" }));
    expect(history.location.pathname).toBe("/inbox/M003");
    expect(await screen.findByText("2 of 3")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "Back to inbox" }));
    expect(await screen.findByRole("list", { name: "Messages" })).toBeInTheDocument();
  });

  it("steps only through the filtered messages", async () => {
    renderRoute("/inbox/M004?filter=attention");
    expect(await screen.findByText("1 of 1")).toBeInTheDocument();
  });

  it("says when a message is not in the dataset", async () => {
    renderRoute("/inbox/M999");
    expect(await screen.findByText("No message M999 in this dataset")).toBeInTheDocument();
  });

  it("re-runs a graded message live with the form pre-filled", async () => {
    const { history } = renderRoute("/inbox/M003");
    await userEvent.click(await screen.findByRole("link", { name: "Re-run live" }));
    expect(history.location.search).toContain("replay=M003");
    expect(await screen.findByText(/Re-running/)).toHaveTextContent(
      "Re-running M003 from the sample run",
    );
    expect(screen.getByLabelText("Message")).toHaveValue(
      "Woke up with crushing chest pain going into my left arm.",
    );
  });

  it("says plainly when a message matches its label", async () => {
    renderRoute("/inbox/M003");
    expect(await screen.findByText("Matches the label")).toBeInTheDocument();
  });
});
