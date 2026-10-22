import { describe, expect, it } from "vitest";

import { CATEGORIES, splitRootCause } from "./rootCause";

describe("splitRootCause", () => {
  it("splits the category from the explanation", () => {
    expect(splitRootCause("By design: the brief says so.")).toEqual({
      category: "By design",
      detail: "the brief says so.",
    });
  });

  it("groups a fixed guard bug and keeps the rest as written", () => {
    expect(splitRootCause("Guard bug, fixed after the run: x").category).toBe("Guard bug (fixed)");
    expect(splitRootCause("Judgement: y").category).toBe("Judgement");
  });

  it("calls a missing or free-text cause unanalysed, never inventing a category", () => {
    expect(splitRootCause(undefined)).toEqual({
      category: "Not analysed",
      detail: "Root cause not yet analysed.",
    });
    expect(
      splitRootCause("A long sentence, with no category before any colon at all here: x").category,
    ).toBe("Other");
  });

  it("orders the known categories with safety-relevant ones first", () => {
    expect(CATEGORIES[0]).toBe("Accepted over-escalation");
  });
});
