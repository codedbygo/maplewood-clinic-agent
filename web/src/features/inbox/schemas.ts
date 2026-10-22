import { z } from "zod";

// Shapes the console API returns for a dataset run. Other features import the
// shared ones (result, trace call, LLM call) from here.

export const urgencySchema = z.enum(["emergency", "urgent", "routine"]);
export type Urgency = z.infer<typeof urgencySchema>;

export const datasetIdSchema = z.enum(["sample", "holdout"]);
export type DatasetId = z.infer<typeof datasetIdSchema>;

export const messageSchema = z.object({
  id: z.string(),
  received_at: z.string().optional(),
  channel: z.string(),
  from_name: z.string(),
  from_contact: z.string(),
  body: z.string(),
  stated_dob: z.string().optional(),
});
export type InboxMessage = z.infer<typeof messageSchema>;

export const labelSchema = z.object({
  id: z.string(),
  patient_id: z.string().nullable(),
  intents: z.array(z.string()),
  accepted_urgency: z.array(urgencySchema),
  expected_actions: z.array(z.string()),
  must_not: z.array(z.string()),
  trap: z.string(),
});
export type Label = z.infer<typeof labelSchema>;

export const resultSchema = z.object({
  id: z.string(),
  patient_id: z.string().nullable(),
  intents: z.array(z.string()),
  urgency: urgencySchema,
  actions: z.array(z.string()),
  routed_to: z.array(z.string()),
  tool_calls: z.array(z.string()),
  reply_draft: z.string(),
});
export type AgentResult = z.infer<typeof resultSchema>;

export const traceCallSchema = z.object({
  name: z.string(),
  input: z.record(z.string(), z.unknown()),
  ok: z.boolean(),
  output: z.record(z.string(), z.unknown()),
});
export type TraceCall = z.infer<typeof traceCallSchema>;

export const screenSchema = z.object({
  tier: z.enum(["emergency", "urgent_clinical", "none"]),
  matches: z.array(z.string()).default([]),
  language: z.string().default("en"),
});
export type Screen = z.infer<typeof screenSchema>;

export const triageSchema = z.object({
  intents: z.array(z.string()),
  urgency: urgencySchema,
  emergency: z.boolean(),
  clinical_concern: z.boolean(),
  rationale: z.string(),
  language: z.string(),
  suspicious_instruction: z.boolean(),
});
export type Triage = z.infer<typeof triageSchema>;

export const llmCallSchema = z.object({
  kind: z.string(),
  model: z.string(),
  input_tokens: z.number(),
  output_tokens: z.number(),
  cache_read_input_tokens: z.number(),
  cache_creation_input_tokens: z.number(),
  latency_s: z.number(),
  stop_reason: z.string().nullable(),
});
export type LlmCall = z.infer<typeof llmCallSchema>;

export const runLogSchema = z.object({
  path: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
  screen: screenSchema.nullable().optional(),
  triage: triageSchema.nullable().optional(),
  verification: z.record(z.string(), z.unknown()).nullable().optional(),
  trace: z.array(traceCallSchema).nullable().optional(),
  guard_violations: z.array(z.string()).nullable().optional(),
  extra_routes: z.array(z.record(z.string(), z.unknown())).nullable().optional(),
  latency_s: z.number().nullable().optional(),
  llm_calls: z.array(llmCallSchema).nullable().optional(),
});
export type RunLog = z.infer<typeof runLogSchema>;

export const messageScoreSchema = z.object({
  id: z.string(),
  urgency_ok: z.boolean(),
  actions_exact: z.boolean(),
  intent_f1: z.number(),
  patient_ok: z.boolean(),
  routing_ok: z.boolean(),
  missing_actions: z.array(z.string()),
  extra_actions: z.array(z.string()),
});
export type MessageScore = z.infer<typeof messageScoreSchema>;

export const inboxItemSchema = z.object({
  message: messageSchema,
  label: labelSchema.nullable(),
  result: resultSchema.nullable(),
  log: runLogSchema.nullable(),
  score: messageScoreSchema.nullable(),
  root_cause: z.string().nullable().optional(),
});
export type InboxItem = z.infer<typeof inboxItemSchema>;

export const runMetaSchema = z.object({
  run_id: z.string(),
  model: z.string(),
  effort: z.string().optional(),
  n: z.number(),
  wall_s: z.number(),
});
export type RunMeta = z.infer<typeof runMetaSchema>;

export const inboxResponseSchema = z.object({
  dataset: datasetIdSchema,
  run: runMetaSchema.nullable(),
  items: z.array(inboxItemSchema),
});
export type InboxResponse = z.infer<typeof inboxResponseSchema>;

export const datasetSchema = z.object({
  id: datasetIdSchema,
  label: z.string(),
  messages: z.number(),
  has_results: z.boolean(),
  has_eval: z.boolean(),
});
export const datasetListSchema = z.array(datasetSchema);
export type Dataset = z.infer<typeof datasetSchema>;

export const healthSchema = z.object({
  ok: z.boolean(),
  provider: z.string().nullable().optional(),
  model: z.string().nullable(),
  effort: z.string().nullable().optional(),
  llm_configured: z.boolean(),
});
export type Health = z.infer<typeof healthSchema>;
