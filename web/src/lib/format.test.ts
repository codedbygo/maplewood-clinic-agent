import { describe, expect, it } from "vitest";

import { actionLabel, clockTime, label, pct, queueLabel, seconds, usd } from "./format";

describe("format", () => {
  it("labels known and unknown vocabulary", () => {
    expect(actionLabel("escalate_emergency")).toBe("Escalate emergency");
    expect(actionLabel("brand_new_action")).toBe("Brand new action");
    expect(queueLabel("clinician_urgent")).toBe("Clinician (urgent)");
    expect(queueLabel("pharmacy")).toBe("Pharmacy");
    expect(label("urgent_clinical")).toBe("Urgent clinical");
  });

  it("formats numbers", () => {
    expect(pct(0.875)).toBe("87.5%");
    expect(usd(0.4213)).toBe("$0.42");
    expect(usd(0.0042)).toBe("$0.0042");
    expect(seconds(3.14159)).toBe("3.1s");
  });

  it("reads the clock time from an ISO timestamp", () => {
    expect(clockTime("2026-11-09T07:02:00-06:00")).toBe("07:02");
    expect(clockTime(undefined)).toBe("");
    expect(clockTime("garbage")).toBe("");
  });
});
