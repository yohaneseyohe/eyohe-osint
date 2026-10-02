"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet } from "@/lib/api";
import type { EventOut } from "@/lib/types";

const MAX_EVENTS = 2000;

export interface FeedState {
  events: EventOut[];
  connected: boolean;
  error: string | null;
}

/**
 * Replays persisted events from the DB, then follows the SSE stream. On drop it
 * reconnects with the last seen seq so nothing is missed or duplicated.
 */
export function useInvestigationFeed(investigationId: string, live: boolean): FeedState {
  const [events, setEvents] = useState<EventOut[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastSeq = useRef(0);

  useEffect(() => {
    let cancelled = false;
    let es: EventSource | null = null;
    let retry: number | null = null;
    let backoff = 1000;

    const append = (incoming: EventOut[]) => {
      if (incoming.length === 0) return;
      setEvents((prev) => {
        const seen = new Set(prev.map((e) => e.seq));
        const fresh = incoming.filter((e) => !seen.has(e.seq));
        if (fresh.length === 0) return prev;
        const next = [...prev, ...fresh].sort((a, b) => a.seq - b.seq);
        return next.length > MAX_EVENTS ? next.slice(next.length - MAX_EVENTS) : next;
      });
      lastSeq.current = Math.max(lastSeq.current, ...incoming.map((e) => e.seq));
    };

    const connect = () => {
      if (cancelled) return;
      es = new EventSource(`/api/v1/investigations/${investigationId}/events/stream?after=${lastSeq.current}`);
      es.addEventListener("open", () => {
        setConnected(true);
        setError(null);
        backoff = 1000;
      });
      es.addEventListener("investigation", (msg) => {
        try {
          append([JSON.parse((msg as MessageEvent<string>).data) as EventOut]);
        } catch {
          // Ignore malformed frames; the next replay will fill any gap.
        }
      });
      es.addEventListener("error", () => {
        setConnected(false);
        es?.close();
        es = null;
        if (cancelled) return;
        retry = window.setTimeout(connect, backoff);
        backoff = Math.min(backoff * 2, 15_000);
      });
    };

    (async () => {
      try {
        const replay = await apiGet<EventOut[]>(`/investigations/${investigationId}/events`, { after: 0, limit: 2000 });
        if (cancelled) return;
        append(replay);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load events");
      }
      if (live) connect();
    })();

    return () => {
      cancelled = true;
      es?.close();
      if (retry) window.clearTimeout(retry);
    };
  }, [investigationId, live]);

  return { events, connected, error };
}
