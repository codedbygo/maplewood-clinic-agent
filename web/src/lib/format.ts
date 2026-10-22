// Display text for the agent's vocabulary and numbers. One place, so every view says the same thing.

const ACTION_LABELS: Record<string, string> = {
  escalate_emergency: "Escalate emergency",
  route_to_clinician: "Route to clinician",
  route_to_provider: "Route to provider",
  route_to_billing: "Route to billing",
  route_to_front_desk: "Route to front desk",
  prepare_refill_for_approval: "Prepare refill for approval",
  refill_needs_visit: "Refill needs visit",
  refill_too_early: "Refill too early",
  book_appointment: "Book appointment",
  reschedule_appointment: "Reschedule",
  cancel_appointment: "Cancel appointment",
  offer_appointment: "Offer appointment",
  offer_alternatives: "Offer alternatives",
  offer_new_patient_booking: "Offer new-patient booking",
  request_verification: "Request verification",
  decline_disclosure: "Decline disclosure",
  flag_suspicious_instruction: "Flag suspicious instruction",
  answer_directly: "Answer directly",
  acknowledge: "Acknowledge",
  no_action: "No action",
};

export const QUEUE_LABELS: Record<string, string> = {
  clinician_urgent: "Clinician (urgent)",
  clinician_routine: "Clinician (routine)",
  provider_refills: "Provider refills",
  front_desk: "Front desk",
  billing: "Billing",
};

export const QUEUE_ORDER = [
  "clinician_urgent",
  "clinician_routine",
  "provider_refills",
  "front_desk",
  "billing",
];

function humanise(key: string): string {
  const text = key.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? humanise(action);
}

export function queueLabel(queue: string): string {
  return QUEUE_LABELS[queue] ?? humanise(queue);
}

export function label(key: string): string {
  return humanise(key);
}

export function pct(x: number): string {
  return `${(x * 100).toFixed(1)}%`;
}

export function usd(x: number): string {
  return x < 0.01 ? `$${x.toFixed(4)}` : `$${x.toFixed(2)}`;
}

export function seconds(x: number): string {
  return `${x.toFixed(1)}s`;
}

/** "07:02" from an ISO timestamp, in the clinic's local offset as written. */
export function clockTime(iso: string | undefined): string {
  if (!iso) return "";
  const match = /T(\d{2}:\d{2})/.exec(iso);
  return match?.[1] ?? "";
}
