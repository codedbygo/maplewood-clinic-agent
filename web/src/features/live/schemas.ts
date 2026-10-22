import { z } from "zod";

import {
  llmCallSchema,
  messageSchema,
  resultSchema,
  screenSchema,
  triageSchema,
} from "@/features/inbox/schemas";

/** The form a staff member fills in to process a new message. */
export const composeSchema = z.object({
  from_name: z.string().trim().min(1, "Sender name is required").max(120),
  from_contact: z.string().trim().min(1, "Phone or email is required").max(120),
  channel: z.enum(["sms", "portal", "email"]),
  body: z.string().trim().min(1, "Message text is required").max(4000),
  stated_dob: z
    .string()
    .trim()
    .regex(/^\d{4}-\d{2}-\d{2}$/, "Use YYYY-MM-DD")
    .optional()
    .or(z.literal("").transform(() => undefined)),
});
export type ComposeValues = z.input<typeof composeSchema>;
export type ComposePayload = z.output<typeof composeSchema>;

/**
 * Server-sent events from POST /api/live/process, in the order they arrive.
 * Stage events share type "stage", so they form their own union on `stage`
 * (Zod 4 rejects a duplicate discriminator value in one union).
 */
const stageEventSchema = z.discriminatedUnion("stage", [
  z.object({ type: z.literal("stage"), stage: z.literal("prescreen"), data: screenSchema }),
  z.object({
    type: z.literal("stage"),
    stage: z.literal("triage"),
    data: triageSchema.nullable(),
    error: z.string().optional(),
  }),
  z.object({
    type: z.literal("stage"),
    stage: z.literal("path"),
    data: z.object({ path: z.string().nullable(), error: z.string().nullable() }),
  }),
]);

export const liveEventSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("message"), data: messageSchema }),
  stageEventSchema,
  z.object({
    type: z.literal("tool"),
    name: z.string(),
    input: z.record(z.string(), z.unknown()),
    ok: z.boolean(),
    output: z.record(z.string(), z.unknown()),
  }),
  z.object({
    type: z.literal("guard"),
    data: z.object({
      violations: z.array(z.string()),
      extra_routes: z.array(z.record(z.string(), z.unknown())),
    }),
  }),
  z.object({
    type: z.literal("result"),
    data: resultSchema,
    latency_s: z.number(),
    llm_calls: z.array(llmCallSchema),
  }),
  z.object({ type: z.literal("error"), error: z.string() }),
]);
export type LiveEvent = z.infer<typeof liveEventSchema>;
