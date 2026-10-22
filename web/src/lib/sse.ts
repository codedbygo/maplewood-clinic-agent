import { ApiError } from "@/lib/api";
import { env } from "@/lib/env";

/**
 * postEventStream POSTs a JSON body and reads a text/event-stream answer,
 * calling onEvent with each `data:` payload parsed as JSON. EventSource only
 * does GET, so this reads the fetch body stream instead. A non-2xx status
 * throws ApiError like apiFetch; a malformed event is skipped, not fatal,
 * because one bad line must not hide the rest of a live run.
 */
export async function postEventStream(
  path: string,
  body: unknown,
  onEvent: (event: unknown) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${env.VITE_API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      ...(signal ? { signal } : {}),
    });
  } catch (cause) {
    throw new ApiError("network", 0, `POST ${path}: network error`, cause);
  }
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new ApiError("http", response.status, `POST ${path}: ${String(response.status)}`, text);
  }
  if (!response.body) {
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const flush = (block: string) => {
    const data = block
      .split("\n")
      .filter((line) => line.startsWith("data: "))
      .map((line) => line.slice(6))
      .join("");
    if (!data) return;
    let event: unknown;
    try {
      event = JSON.parse(data);
    } catch {
      return; // Skip a malformed event; the stream continues.
    }
    onEvent(event); // Consumer errors propagate: a bug there must not look like silence.
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut = buffer.indexOf("\n\n");
    while (cut !== -1) {
      flush(buffer.slice(0, cut));
      buffer = buffer.slice(cut + 2);
      cut = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) flush(buffer);
}
