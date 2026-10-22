import { z } from "zod";

import { messageScoreSchema } from "@/features/inbox/schemas";

const prfSchema = z.object({
  precision: z.number(),
  recall: z.number(),
  f1: z.number(),
  tp: z.number(),
  fp: z.number(),
  fn: z.number(),
});
export type Prf = z.infer<typeof prfSchema>;

export const evalReportSchema = z.object({
  models_served: z.record(z.string(), z.number()).optional(),
  meta: z.object({
    run_id: z.string(),
    model: z.string(),
    effort: z.string().optional(),
    messages: z.string(),
    n: z.number(),
    wall_s: z.number(),
  }),
  scores: z.object({
    n: z.number(),
    urgency_accuracy: z.number(),
    emergency: z.object({
      n_labelled: z.number(),
      recall: z.number(),
      precision: z.number(),
      missed: z.array(z.string()),
      over_escalated: z.array(z.string()),
    }),
    actions: z.object({
      exact_match: z.number(),
      micro: prfSchema,
      macro_f1: z.number(),
      per_action: z.record(z.string(), prfSchema),
    }),
    intent_f1: z.number(),
    patient_id_accuracy: z.number(),
    routing_accuracy: z.number(),
    per_message: z.array(messageScoreSchema),
  }),
  must_not_violations: z.array(z.object({ id: z.string(), tag: z.string(), evidence: z.string() })),
  global_safety: z.array(z.object({ id: z.string(), check: z.string(), evidence: z.string() })),
  cost: z.object({
    total_usd: z.number(),
    mean_usd_per_message: z.number(),
    tokens: z.record(z.string(), z.number()),
  }),
  latency: z.object({ p50_s: z.number(), p95_s: z.number(), max_s: z.number() }),
  paths: z.record(z.string(), z.number()),
  guard_interventions: z.record(z.string(), z.array(z.string())),
  root_causes: z.record(z.string(), z.string()),
});
export type EvalReport = z.infer<typeof evalReportSchema>;

export const stabilitySchema = z.object({
  runs: z.number(),
  messages: z.number(),
  changed: z.number(),
  changed_ids: z.array(z.string()),
  emergency_flips: z.array(z.string()),
  model: z.string().nullable().optional(),
  complete: z.boolean().optional(),
});
export type Stability = z.infer<typeof stabilitySchema>;
