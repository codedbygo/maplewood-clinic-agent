import { z } from "zod";

// Clinic store state: the live session's, or a finished run's final state.

export const appointmentSchema = z.object({
  id: z.string(),
  patient_id: z.string(),
  provider: z.string(),
  date: z.string(),
  start: z.string(),
  end: z.string(),
  visit_type: z.string(),
  status: z.string(),
  message_id: z.string().nullable().optional(),
});
export type Appointment = z.infer<typeof appointmentSchema>;

export const routeSchema = z.object({
  queue: z.string(),
  priority: z.string().default("routine"),
  summary: z.string().default(""),
  patient_id: z.string().nullable().optional(),
  message_id: z.string().nullable().optional(),
});
export type QueueRoute = z.infer<typeof routeSchema>;

export const refillRequestSchema = z.object({
  id: z.string(),
  patient_id: z.string(),
  medication: z.string(),
  prescriber: z.string().nullable().optional(),
  status: z.string(),
  note: z.string().default(""),
  message_id: z.string().nullable().optional(),
});
export type RefillRequest = z.infer<typeof refillRequestSchema>;

export const flagSchema = z.object({
  excerpt: z.string(),
  why: z.string(),
  message_id: z.string().nullable().optional(),
});
export type Flag = z.infer<typeof flagSchema>;

export const clinicStateSchema = z.object({
  appointments: z.array(appointmentSchema).default([]),
  refill_requests: z.array(refillRequestSchema).default([]),
  routes: z.array(routeSchema).default([]),
  flags: z.array(flagSchema).default([]),
});
export type ClinicState = z.infer<typeof clinicStateSchema>;

export const stateSourceSchema = z.enum(["live", "sample", "holdout"]);
export type StateSource = z.infer<typeof stateSourceSchema>;

const leaveSchema = z.tuple([z.string(), z.string()]);

export const providerSchema = z.object({
  id: z.string(),
  name: z.string(),
  role: z.string(),
  languages: z.array(z.string()),
  leave: z.array(leaveSchema).optional(),
});
export type Provider = z.infer<typeof providerSchema>;

export const clinicInfoSchema = z.object({
  clinic: z.object({
    clinic_name: z.string(),
    today: z.string(),
    hours: z.object({
      days: z.array(z.string()),
      open: z.string(),
      close: z.string(),
      lunch: z.tuple([z.string(), z.string()]),
    }),
    holidays: z.array(z.string()),
    providers: z.array(providerSchema),
    visit_types: z.record(z.string(), z.number()),
  }),
  patients: z.array(z.object({ id: z.string(), name: z.string(), primary_provider: z.string() })),
});
export type ClinicInfo = z.infer<typeof clinicInfoSchema>;
