import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderRoute } from "@/test/app";

describe("SchedulePage", () => {
  it("shows today's grid with agent changes highlighted", async () => {
    renderRoute("/schedule");
    const patel = await screen.findByRole("region", { name: "Dr. Maya Patel on 2026-11-09" });
    expect(patel).toHaveTextContent("10:00 Grace Park");
    expect(patel).toHaveTextContent("booked by agent (M010)");
    expect(screen.getByRole("region", { name: "Sarah Kim, NP on 2026-11-09" })).toHaveTextContent(
      "cancelled by agent (M022)",
    );
  });

  it("lists agent changes and jumps to their day", async () => {
    renderRoute("/schedule");
    expect(await screen.findByText("Agent changes in this session (2)")).toBeInTheDocument();
  });

  it("shows provider leave", async () => {
    renderRoute("/schedule?date=2026-11-18");
    const okafor = await screen.findByRole("region", { name: "Dr. James Okafor on 2026-11-18" });
    expect(within(okafor).getByText("On leave")).toBeInTheDocument();
  });

  it("shows holidays as closed", async () => {
    renderRoute("/schedule?date=2026-11-23");
    await userEvent.click(await screen.findByRole("button", { name: /Thu, Nov 26/ }));
    expect(await screen.findByText(/Clinic closed on Thu, Nov 26 \(holiday\)/)).toBeInTheDocument();
  });

  it("ignores a malformed date in the URL", async () => {
    renderRoute("/schedule?date=yesterday");
    expect(
      await screen.findByRole("region", { name: "Dr. Maya Patel on 2026-11-09" }),
    ).toBeInTheDocument();
  });
});
