import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderRoute } from "@/test/app";

describe("App", () => {
  it("renders the live console at the root with the main navigation", async () => {
    renderRoute("/");
    expect(await screen.findByRole("heading", { name: "Live console" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Main" });
    for (const name of ["Live console", "Inbox", "Staff queues", "Schedule", "Evaluation"]) {
      expect(nav).toContainElement(screen.getByRole("link", { name }));
    }
  });

  it("shows the model status from the API", async () => {
    renderRoute("/");
    expect(await screen.findByText("claude-sonnet-5-5")).toBeInTheDocument();
  });

  it("navigates between pages", async () => {
    renderRoute("/");
    await userEvent.click(await screen.findByRole("link", { name: "Evaluation" }));
    expect(await screen.findByRole("heading", { name: "Evaluation" })).toBeInTheDocument();
  });

  it("toggles the dark theme on the document", async () => {
    renderRoute("/");
    await userEvent.click(await screen.findByRole("button", { name: "Switch to dark theme" }));
    expect(document.documentElement).toHaveClass("dark");
    await userEvent.click(screen.getByRole("button", { name: "Switch to light theme" }));
    expect(document.documentElement).not.toHaveClass("dark");
  });

  it("renders the not-found route for an unknown path", async () => {
    renderRoute("/nowhere");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
