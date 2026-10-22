import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { server } from "@/test/msw";

import { postEventStream } from "./sse";

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
}

describe("postEventStream", () => {
  it("parses data events split across chunks", async () => {
    server.use(
      http.post(
        "*/api/stream",
        () =>
          new HttpResponse(streamOf(['data: {"type":"a"}\n\nda', 'ta: {"type":"b","n":1}\n\n']), {
            headers: { "Content-Type": "text/event-stream" },
          }),
      ),
    );
    const seen: unknown[] = [];
    await postEventStream("/api/stream", { x: 1 }, (e) => seen.push(e));
    expect(seen).toEqual([{ type: "a" }, { type: "b", n: 1 }]);
  });

  it("throws ApiError with the status on a non-2xx answer", async () => {
    server.use(
      http.post("*/api/stream", () => HttpResponse.json({ error: "bad" }, { status: 422 })),
    );
    await expect(postEventStream("/api/stream", {}, () => undefined)).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
    });
  });

  it("throws a network ApiError when the request fails", async () => {
    server.use(http.post("*/api/stream", () => HttpResponse.error()));
    await expect(postEventStream("/api/stream", {}, () => undefined)).rejects.toBeInstanceOf(
      ApiError,
    );
  });

  it("skips malformed events instead of failing the run", async () => {
    server.use(
      http.post(
        "*/api/stream",
        () => new HttpResponse(streamOf(["data: not-json\n\n", 'data: {"ok":true}\n\n'])),
      ),
    );
    const seen: unknown[] = [];
    await postEventStream("/api/stream", {}, (e) => seen.push(e));
    expect(seen).toEqual([{ ok: true }]);
  });
});

describe("postEventStream consumer errors", () => {
  it("does not swallow an exception thrown by the consumer", async () => {
    server.use(
      http.post("*/api/stream", () => new HttpResponse(streamOf(['data: {"ok":true}\n\n']))),
    );
    await expect(
      postEventStream("/api/stream", {}, () => {
        throw new Error("consumer bug");
      }),
    ).rejects.toThrow("consumer bug");
  });
});
