import type { Provider } from "@/features/state/schemas";

// Display helpers for the schedule grid. Booking policy lives in the MCP tools;
// these only place already-booked appointments on screen.

const SLOT_MINUTES = 20;

function minutes(hhmm: string): number {
  const [h = "0", m = "0"] = hhmm.split(":");
  return Number(h) * 60 + Number(m);
}

export function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

function mondayOf(iso: string): string {
  const day = new Date(`${iso}T00:00:00Z`).getUTCDay(); // 0 = Sunday
  return addDays(iso, -((day + 6) % 7));
}

/** The three weeks the appointment data covers, from the Monday of the clinic's today. */
export function weekStarts(today: string): string[] {
  const monday = mondayOf(today);
  return [0, 7, 14].map((n) => addDays(monday, n));
}

export function weekDays(monday: string): string[] {
  return [0, 1, 2, 3, 4].map((n) => addDays(monday, n));
}

export function slotRow(start: string, open: string): number {
  return (minutes(start) - minutes(open)) / SLOT_MINUTES + 1;
}

export function rowSpan(start: string, end: string): number {
  return Math.max(1, (minutes(end) - minutes(start)) / SLOT_MINUTES);
}

export function timeLabels(open: string, close: string): string[] {
  const out: string[] = [];
  for (let t = minutes(open); t < minutes(close); t += SLOT_MINUTES) {
    out.push(`${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`);
  }
  return out;
}

export function onLeave(provider: Provider, date: string): boolean {
  return (provider.leave ?? []).some(([from, to]) => from <= date && date <= to);
}

export function weekdayName(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
