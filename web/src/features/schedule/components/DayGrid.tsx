import type { Appointment, ClinicInfo } from "@/features/state/schemas";
import { label } from "@/lib/format";
import { cn } from "@/lib/utils";

import { onLeave, rowSpan, slotRow, timeLabels } from "../grid";

interface Props {
  date: string;
  clinic: ClinicInfo["clinic"];
  appointments: Appointment[];
  nameOf: (id: string) => string | undefined;
}

/** DayGrid: one clinic day, a column per provider, 20-minute rows. Agent changes are highlighted. */
export function DayGrid({ date, clinic, appointments, nameOf }: Props) {
  const { open, close, lunch } = clinic.hours;
  const times = timeLabels(open, close);
  const lunchRow = slotRow(lunch[0], open);
  const lunchSpan = rowSpan(lunch[0], lunch[1]);
  // One fixed row height for every column, so a two-line booking never pushes a column out of line.
  const rows = { gridTemplateRows: `repeat(${String(times.length)}, 2.5rem)` };

  return (
    <div className="overflow-x-auto rounded-lg border">
      <div className="flex min-w-fit">
        <div aria-hidden className="w-16 shrink-0 border-r bg-muted/40 pt-10">
          <div className="grid" style={rows}>
            {times.map((t) => (
              <div
                key={t}
                className="border-t px-2 pt-0.5 text-xs text-muted-foreground tabular-nums"
              >
                {t.endsWith(":00") ? t : ""}
              </div>
            ))}
          </div>
        </div>
        {clinic.providers.map((p) => {
          const leave = onLeave(p, date);
          const mine = appointments.filter((a) => a.provider === p.id && a.date === date);
          return (
            <section
              key={p.id}
              aria-label={`${p.name} on ${date}`}
              className="min-w-56 flex-1 border-r last:border-r-0"
            >
              <h3 className="h-10 truncate border-b px-3 py-2 text-sm font-semibold">{p.name}</h3>
              <div className="relative grid" style={rows}>
                {times.map((t) => (
                  <div
                    key={t}
                    aria-hidden
                    className="border-t border-dashed"
                    style={{ gridRow: slotRow(t, open), gridColumn: 1 }}
                  />
                ))}
                <div
                  aria-hidden
                  className="flex items-center justify-center bg-muted text-xs text-muted-foreground"
                  style={{
                    gridRow: `${String(lunchRow)} / span ${String(lunchSpan)}`,
                    gridColumn: 1,
                  }}
                >
                  Lunch
                </div>
                {leave && (
                  <div
                    className="flex items-center justify-center bg-warning/15 text-sm font-medium"
                    style={{ gridRow: `1 / span ${String(times.length)}`, gridColumn: 1 }}
                  >
                    On leave
                  </div>
                )}
                {mine.map((a) => {
                  const byAgent = Boolean(a.message_id);
                  const cancelled = a.status !== "booked";
                  return (
                    <div
                      key={a.id}
                      className={cn(
                        "z-10 m-0.5 overflow-hidden rounded-md border px-2 py-0.5 text-xs leading-tight",
                        byAgent ? "border-primary bg-primary/15 ring-2 ring-primary/40" : "bg-card",
                        cancelled && "border-dashed bg-transparent opacity-70",
                      )}
                      style={{
                        gridRow: `${String(slotRow(a.start, open))} / span ${String(rowSpan(a.start, a.end))}`,
                        gridColumn: 1,
                      }}
                    >
                      <p className={cn("font-medium", cancelled && "line-through")}>
                        {a.start} {nameOf(a.patient_id) ?? a.patient_id}
                      </p>
                      <p className="text-muted-foreground">
                        {label(a.visit_type)}
                        {byAgent && (
                          <span className="font-medium text-primary">
                            {" "}
                            · {cancelled ? "cancelled" : "booked"} by agent ({a.message_id})
                          </span>
                        )}
                      </p>
                    </div>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
