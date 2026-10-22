import { CalendarX } from "lucide-react";

import { PageHeader } from "@/components/PageHeader";
import { Empty, Pending, QueryError } from "@/components/QueryState";
import { Segmented } from "@/components/Segmented";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useClinicInfo, useClinicState, usePatientNames } from "@/features/state/hooks";
import type { StateSource } from "@/features/state/schemas";
import { SOURCES } from "@/features/state/sources";
import { label } from "@/lib/format";

import { weekDays, weekdayName, weekStarts } from "../grid";
import { DayGrid } from "./DayGrid";

export interface ScheduleSearch {
  source: StateSource;
  date?: string | undefined;
}

/** SchedulePage: provider calendars with hours, lunch, holidays and leave, and every agent change highlighted. */
export function SchedulePage({
  search,
  onSearch,
}: {
  search: ScheduleSearch;
  onSearch: (next: Partial<ScheduleSearch>) => void;
}) {
  const info = useClinicInfo();
  const state = useClinicState(search.source);
  const names = usePatientNames();
  const nameOf = (id: string) => names.data?.get(id);

  let body;
  if (info.isPending || state.isPending) body = <Pending label="Loading schedule" />;
  else if (info.isError)
    body = <QueryError error={info.error} onRetry={() => void info.refetch()} />;
  else if (state.isError)
    body = (
      <QueryError
        error={state.error}
        onRetry={() => void state.refetch()}
        notFound={<p>No store for this run yet.</p>}
      />
    );
  else {
    const clinic = info.data.clinic;
    const weeks = weekStarts(clinic.today);
    const date = search.date ?? clinic.today;
    const week = weeks.find((w) => weekDays(w).includes(date)) ?? weeks[0] ?? clinic.today;
    const changes = state.data.appointments
      .filter((a) => a.message_id)
      .sort((a, b) => (a.date + a.start).localeCompare(b.date + b.start));
    const holiday = clinic.holidays.includes(date);
    body = (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Segmented
            label="Week"
            value={week}
            onChange={(w) => {
              onSearch({ date: w });
            }}
            options={weeks.map((w) => ({ value: w, label: `Week of ${weekdayName(w)}` }))}
          />
        </div>
        <nav aria-label="Days" className="flex flex-wrap gap-1.5">
          {weekDays(week).map((d) => {
            const count = changes.filter((a) => a.date === d).length;
            return (
              <button
                key={d}
                type="button"
                aria-current={d === date ? "date" : undefined}
                onClick={() => {
                  onSearch({ date: d });
                }}
                className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none aria-[current=date]:border-primary aria-[current=date]:bg-accent"
              >
                {weekdayName(d)}
                {clinic.holidays.includes(d) && <Badge variant="outline">Holiday</Badge>}
                {count > 0 && <Badge>{count}</Badge>}
              </button>
            );
          })}
        </nav>
        {holiday ? (
          <Empty title={`Clinic closed on ${weekdayName(date)} (holiday)`}>
            Nothing can be booked; the booking tools refuse it.
          </Empty>
        ) : (
          <DayGrid
            date={date}
            clinic={clinic}
            appointments={state.data.appointments}
            nameOf={nameOf}
          />
        )}
        <Card className="gap-3">
          <CardHeader>
            <CardTitle className="text-base">
              Agent changes in this {search.source === "live" ? "session" : "run"} ({changes.length}
              )
            </CardTitle>
          </CardHeader>
          <CardContent>
            {changes.length ? (
              <ul className="divide-y text-sm">
                {changes.map((a) => (
                  <li key={a.id}>
                    <button
                      type="button"
                      onClick={() => {
                        onSearch({ date: a.date });
                      }}
                      className="flex w-full flex-wrap items-center gap-2 py-2 text-left hover:text-primary"
                    >
                      <span className="font-mono text-xs text-muted-foreground">
                        {a.message_id}
                      </span>
                      <span className="font-medium">{nameOf(a.patient_id) ?? a.patient_id}</span>
                      <span>
                        {label(a.visit_type)} with {a.provider}, {weekdayName(a.date)} {a.start}
                      </span>
                      <Badge
                        variant={a.status === "booked" ? "secondary" : "outline"}
                        className="ml-auto"
                      >
                        {a.status === "booked" ? "booked or moved" : a.status}
                      </Badge>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <CalendarX aria-hidden className="size-4" /> No bookings, moves or cancellations
                yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Schedule"
        description="Hours, lunch, holidays and leave as the tools enforce them. Agent changes are outlined."
      >
        <Segmented
          label="Data source"
          value={search.source}
          onChange={(source) => {
            onSearch({ source });
          }}
          options={SOURCES}
        />
      </PageHeader>
      {body}
    </div>
  );
}
