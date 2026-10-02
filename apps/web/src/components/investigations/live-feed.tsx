"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDown, Pause, Play, Radio } from "lucide-react";
import { useInvestigationFeed } from "@/hooks/use-investigation-feed";
import { useUiStore } from "@/lib/store";
import type { EventOut } from "@/lib/types";
import { formatTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { StageChip } from "@/components/shared/badges";
import { cn } from "@/lib/utils";

function EventRow({ e }: { e: EventOut }) {
  const level = e.level?.toLowerCase();
  const url = typeof e.data?.url === "string" ? e.data.url : null;
  return (
    <li
      className={cn(
        "flex items-start gap-2 border-l-2 border-transparent px-2 py-1 font-mono text-xs animate-slide-in",
        level === "warning" && "border-warning/60 bg-warning/5",
        level === "error" && "border-danger/60 bg-danger/5",
      )}
    >
      <span className="shrink-0 text-fg-subtle" title={e.created_at}>{formatTime(e.created_at)}</span>
      <StageChip value={e.stage} />
      <div className="min-w-0 flex-1">
        <span className={cn("font-sans text-fg-muted", level === "warning" && "text-warning", level === "error" && "text-danger", e.event_type === "FINDING_CREATED" && "text-success")}>
          {e.message}
        </span>
        {url ? <span className="ml-2 truncate text-[10px] text-fg-subtle">{url}</span> : null}
      </div>
      <span className="shrink-0 text-[10px] uppercase text-fg-subtle">{e.event_type.replace(/_/g, " ").toLowerCase()}</span>
    </li>
  );
}

export function LiveFeed({ investigationId, live }: { investigationId: string; live: boolean }) {
  const { events, connected, error } = useInvestigationFeed(investigationId, live);
  const paused = useUiStore((s) => s.feedPaused);
  const setPaused = useUiStore((s) => s.setFeedPaused);
  const [hovering, setHovering] = useState(false);
  const viewport = useRef<HTMLDivElement>(null);
  const autoScroll = !paused && !hovering;

  useEffect(() => {
    if (!autoScroll || !viewport.current) return;
    viewport.current.scrollTop = viewport.current.scrollHeight;
  }, [events.length, autoScroll]);

  return (
    <Card className="flex h-[520px] flex-col">
      <CardHeader className="py-2">
        <CardTitle className="flex items-center gap-2">
          <Radio className={cn("size-3.5", connected ? "text-success" : live ? "text-warning" : "text-fg-subtle")} />
          Live investigation feed
          <span className="font-mono text-[10px] normal-case tracking-normal text-fg-subtle">
            {events.length} events · {live ? (connected ? "streaming" : "reconnecting…") : "replay"}
          </span>
        </CardTitle>
        <div className="flex items-center gap-1">
          {hovering && !paused ? <span className="text-[10px] text-fg-subtle">auto-scroll paused on hover</span> : null}
          <Button variant="ghost" size="icon-xs" onClick={() => setPaused(!paused)} aria-label={paused ? "Resume auto-scroll" : "Pause auto-scroll"}>
            {paused ? <Play /> : <Pause />}
          </Button>
          <Button variant="ghost" size="icon-xs" aria-label="Jump to latest" onClick={() => { if (viewport.current) viewport.current.scrollTop = viewport.current.scrollHeight; }}>
            <ArrowDown />
          </Button>
        </div>
      </CardHeader>
      <div ref={viewport} className="min-h-0 flex-1 overflow-y-auto py-1" onMouseEnter={() => setHovering(true)} onMouseLeave={() => setHovering(false)} role="log" aria-live="polite" aria-relevant="additions">
        {error ? <p className="px-3 py-2 text-xs text-danger">{error}</p> : null}
        {events.length === 0 && !error ? <p className="px-3 py-6 text-center text-xs text-fg-subtle">No events yet. Events appear as soon as the plan is approved and tasks begin.</p> : null}
        <ul>{events.map((e) => <EventRow key={e.seq} e={e} />)}</ul>
      </div>
    </Card>
  );
}
