import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderRoute } from "@/test/app";
import { server } from "@/test/msw";

describe("InboxPage", () => {
  it("lists messages and opens the first one", async () => {
    renderRoute("/inbox");
    const list = await screen.findByRole("list", { name: "Messages" });
    expect(within(list).getAllByRole("button")).toHaveLength(3);
    expect(screen.getByRole("heading", { name: /Robert Chen/ })).toBeInTheDocument();
    expect(screen.getByText(/Run 20261022T100000Z/)).toBeInTheDocument();
  });

  it("marks emergencies and verdicts in the list", async () => {
    renderRoute("/inbox");
    await screen.findByRole("list", { name: "Messages" });
    expect(screen.getByLabelText("Emergency")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Matches label")).toHaveLength(2);
    expect(screen.getByLabelText("Differs from label")).toBeInTheDocument();
  });

  it("filters to messages that differ from the label and shows the root cause", async () => {
    const { history } = renderRoute("/inbox");
    await userEvent.click(await screen.findByRole("radio", { name: "Differs from label (1)" }));
    const list = screen.getByRole("list", { name: "Messages" });
    expect(within(list).getAllByRole("button")).toHaveLength(1);
    expect(screen.getByText(/Policy says route to provider/)).toBeInTheDocument();
    expect(screen.getByText("Routing differs")).toBeInTheDocument();
    expect(history.location.search).toContain("filter=attention");
  });

  it("selects a message by URL and shows the emergency detail", async () => {
    renderRoute("/inbox?id=M003");
    expect(
      await screen.findByText(/crushing chest pain/, { selector: "blockquote" }),
    ).toBeInTheDocument();
    expect(screen.getByText("emergency path")).toBeInTheDocument();
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
