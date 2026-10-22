import { describe, expect, it } from "vitest";

import { fixtureClinic } from "@/test/fixtures";

import { addDays, onLeave, rowSpan, slotRow, timeLabels, weekDays, weekStarts } from "./grid";

describe("schedule grid helpers", () => {
  it("lists the five clinic days of a week", () => {
    expect(weekDays("2026-11-23")).toEqual([
      "2026-11-23",
      "2026-11-24",
      "2026-11-25",
      "2026-11-26",
      "2026-11-27",
    ]);
  });

  it("adds days across a month boundary", () => {
    expect(addDays("2026-11-30", 2)).toBe("2026-12-02");
  });

  it("offers three weeks starting from the Monday of today", () => {
    expect(weekStarts("2026-11-11")).toEqual(["2026-11-09", "2026-11-16", "2026-11-23"]);
  });

  it("maps times to 20-minute grid rows", () => {
    expect(slotRow("09:00", "09:00")).toBe(1);
    expect(slotRow("12:20", "09:00")).toBe(11);
    expect(rowSpan("09:20", "10:00")).toBe(2);
    expect(timeLabels("09:00", "17:00")).toHaveLength(24);
    expect(timeLabels("09:00", "17:00")[0]).toBe("09:00");
  });

  it("knows provider leave", () => {
    const okafor = fixtureClinic().clinic.providers[1];
    expect(okafor && onLeave(okafor, "2026-11-18")).toBe(true);
    expect(okafor && onLeave(okafor, "2026-11-23")).toBe(false);
  });
});
