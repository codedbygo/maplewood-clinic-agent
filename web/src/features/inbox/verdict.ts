import type { InboxItem } from "./schemas";

/** isCorrect: true when every scored field matches the label, null when the message was not scored. */
export function isCorrect(item: InboxItem): boolean | null {
  const s = item.score;
  if (!s) return null;
  return s.urgency_ok && s.actions_exact && s.patient_ok && s.routing_ok && s.intent_f1 === 1;
}
