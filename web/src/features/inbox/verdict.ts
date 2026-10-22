import type { InboxItem } from "./schemas";

/** isCorrect: true when every scored field matches the label, null when the message was not scored. */
export function isCorrect(item: InboxItem): boolean | null {
  const s = item.score;
  if (!s) return null;
  return s.urgency_ok && s.actions_exact && s.patient_ok && s.routing_ok && s.intent_f1 === 1;
}

export type InboxFilter = "all" | "attention" | "emergency";

/** applyFilter: the messages a filter shows. Emergencies include ones the label expects, so a miss still shows. */
export function applyFilter(items: InboxItem[], filter: InboxFilter): InboxItem[] {
  if (filter === "attention") return items.filter((i) => isCorrect(i) === false);
  if (filter === "emergency")
    return items.filter(
      (i) =>
        (i.result?.actions.includes("escalate_emergency") ?? false) ||
        (i.label?.expected_actions.includes("escalate_emergency") ?? false),
    );
  return items;
}
