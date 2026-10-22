import { Loader2, Play } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { EXAMPLES } from "../examples";
import { composeSchema, type ComposePayload, type ComposeValues } from "../schemas";

const EMPTY: ComposeValues = {
  from_name: "",
  from_contact: "",
  channel: "sms",
  body: "",
  stated_dob: "",
};
type Errors = Partial<Record<keyof ComposeValues, string>>;
const CHANNELS = ["sms", "portal", "email"] as const;

function isField(key: unknown): key is keyof ComposeValues {
  return typeof key === "string" && key in EMPTY;
}

function isChannel(value: string): value is ComposeValues["channel"] {
  return (CHANNELS as readonly string[]).includes(value);
}

/** ComposeForm: a new inbound message, validated with Zod before it reaches the agent. */
export function ComposeForm({
  running,
  onSubmit,
  initial,
}: {
  running: boolean;
  onSubmit: (payload: ComposePayload) => void;
  /** Pre-filled values (a replayed message); the parent remounts the form with a key to apply new ones. */
  initial?: ComposeValues | undefined;
}) {
  const [values, setValues] = useState<ComposeValues>(initial ?? EMPTY);
  const [errors, setErrors] = useState<Errors>({});

  function set<K extends keyof ComposeValues>(key: K, value: ComposeValues[K]) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  function submit(event: { preventDefault: () => void }) {
    event.preventDefault();
    const parsed = composeSchema.safeParse(values);
    if (!parsed.success) {
      const next: Errors = {};
      for (const issue of parsed.error.issues) {
        const key = issue.path[0];
        if (isField(key)) next[key] = issue.message;
      }
      setErrors(next);
      return;
    }
    setErrors({});
    onSubmit(parsed.data);
  }

  const field = (key: keyof ComposeValues) =>
    errors[key] ? { "aria-invalid": true, "aria-describedby": `${key}-error` } : {};
  const error = (key: keyof ComposeValues) =>
    errors[key] ? (
      <p id={`${key}-error`} className="text-xs text-destructive">
        {errors[key]}
      </p>
    ) : null;

  return (
    <form onSubmit={submit} noValidate className="space-y-4" aria-label="New message">
      <fieldset className="space-y-2">
        <legend className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Try an example
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLES.map((ex) => (
            <Button
              key={ex.title}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setValues({ ...EMPTY, ...ex.values });
                setErrors({});
              }}
            >
              {ex.title}
            </Button>
          ))}
        </div>
      </fieldset>
      {/* items-end keeps paired inputs on one line when one label wraps to two. */}
      <div className="grid gap-3 sm:grid-cols-2 sm:items-end">
        <div className="space-y-1.5">
          <Label htmlFor="from_name">Sender name</Label>
          <Input
            id="from_name"
            value={values.from_name}
            onChange={(e) => {
              set("from_name", e.target.value);
            }}
            {...field("from_name")}
          />
          {error("from_name")}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="from_contact">Phone or email</Label>
          <Input
            id="from_contact"
            value={values.from_contact}
            onChange={(e) => {
              set("from_contact", e.target.value);
            }}
            {...field("from_contact")}
          />
          {error("from_contact")}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="channel">Channel</Label>
          <select
            id="channel"
            value={values.channel}
            onChange={(e) => {
              if (isChannel(e.target.value)) set("channel", e.target.value);
            }}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <option value="sms">SMS</option>
            <option value="portal">Portal</option>
            <option value="email">Email</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="stated_dob">Stated date of birth (optional)</Label>
          <Input
            id="stated_dob"
            placeholder="YYYY-MM-DD"
            value={values.stated_dob ?? ""}
            onChange={(e) => {
              set("stated_dob", e.target.value);
            }}
            {...field("stated_dob")}
          />
          {error("stated_dob")}
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="body">Message</Label>
        <Textarea
          id="body"
          rows={5}
          value={values.body}
          onChange={(e) => {
            set("body", e.target.value);
          }}
          {...field("body")}
        />
        {error("body")}
      </div>
      <Button type="submit" disabled={running} className="w-full sm:w-auto">
        {running ? <Loader2 aria-hidden className="animate-spin" /> : <Play aria-hidden />}
        {running ? "Processing" : "Process message"}
      </Button>
    </form>
  );
}
