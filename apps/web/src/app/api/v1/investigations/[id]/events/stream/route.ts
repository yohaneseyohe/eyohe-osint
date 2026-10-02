import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

/**
 * SSE passthrough. Node only flushes response headers on the first body write,
 * so behind the generic rewrite proxy EventSource's `open` waits for the first
 * upstream event (up to one 15s server ping). Here we emit an SSE comment as the
 * very first chunk - ignored by EventSource - so headers leave immediately, then
 * pipe the upstream body through untouched.
 */
export async function GET(req: NextRequest, ctx: RouteContext<"/api/v1/investigations/[id]/events/stream">) {
  const { id } = await ctx.params;
  const upstreamUrl = new URL(`/api/v1/investigations/${encodeURIComponent(id)}/events/stream`, API_INTERNAL_URL);
  upstreamUrl.search = req.nextUrl.search;

  const upstream = await fetch(upstreamUrl, {
    headers: {
      accept: "text/event-stream",
      cookie: req.headers.get("cookie") ?? "",
      "last-event-id": req.headers.get("last-event-id") ?? "",
    },
    cache: "no-store",
    signal: req.signal,
  });

  if (!upstream.ok || !upstream.body) {
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  }

  const reader = upstream.body.getReader();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(": connected\n\n"));
    },
    async pull(controller) {
      const { done, value } = await reader.read();
      if (done) controller.close();
      else controller.enqueue(value);
    },
    cancel(reason) {
      void reader.cancel(reason);
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "x-accel-buffering": "no",
    },
  });
}
