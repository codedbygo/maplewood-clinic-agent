import type { EvalReport } from "./schemas";

/**
 * Root causes are written "Category: explanation" in eval/root_causes.json. The category groups the
 * differences on the Evaluation page; the order puts safety-relevant causes first.
 */
export const CATEGORIES = [
  "Accepted over-escalation",
  "Guard bug (fixed)",
  "Judgement",
  "Model variance",
  "By design",
  "Intents only",
  "Other",
  "Not analysed",
] as const;
export type Category = (typeof CATEGORIES)[number];

export function splitRootCause(text: string | undefined): { category: Category; detail: string } {
  if (!text) return { category: "Not analysed", detail: "Root cause not yet analysed." };
  const at = text.indexOf(": ");
  const head = at > 0 ? text.slice(0, at) : "";
  const detail = at > 0 ? text.slice(at + 2) : text;
  if (head.startsWith("Guard bug")) return { category: "Guard bug (fixed)", detail };
  const known = CATEGORIES.find((c) => c === head);
  return known ? { category: known, detail } : { category: "Other", detail: text };
}

/** differs: true when any scored field of a message does not match its label. */
export function differs(m: EvalReport["scores"]["per_message"][number]): boolean {
  return !(m.urgency_ok && m.actions_exact && m.patient_ok && m.routing_ok && m.intent_f1 === 1);
}
