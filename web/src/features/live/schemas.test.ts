import { describe, expect, it } from "vitest";

import { liveRunEvents } from "@/test/msw";

import { composeSchema, liveEventSchema } from "./schemas";

describe("liveEventSchema", () => {
  it("parses every event kind the server emits", () => {
    for (const e of [
      ...liveRunEvents,
      { type: "error", error: "x" },
      { type: "stage", stage: "triage", data: null, error: "no key" },
    ]) {
      expect(liveEventSchema.safeParse(e).success).toBe(true);
    }
  });

  it("rejects an unknown event", () => {
    expect(liveEventSchema.safeParse({ type: "stage", stage: "mystery", data: {} }).success).toBe(
      false,
    );
  });
});

describe("composeSchema", () => {
  it("treats an empty date of birth as absent and trims text", () => {
    const parsed = composeSchema.parse({
      from_name: " A ",
      from_contact: "1",
      channel: "sms",
      body: " hi ",
      stated_dob: "",
    });
    expect(parsed).toEqual({
      from_name: "A",
      from_contact: "1",
      channel: "sms",
      body: "hi",
      stated_dob: undefined,
    });
  });
});
