"use client";

import Link from "next/link";
import { ArrowRight, Play } from "lucide-react";
import type { DashboardOut } from "@/lib/types";
import { formatRelative, formatTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { ConfidenceBadge, InvestigationStatusChip, StageChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { EmptyState } from "@/components/shared/states";
import { cn } from "@/lib/utils";

export function ActiveInvestigations({ items, onNew }: { items: DashboardOut["active_investigations"]; onNew: () => void }) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="No investigations yet — start one"
        description="Pick a target and Eyohe drafts a plan you approve before anything runs."
        action={
          <Button size="sm" onClick={onNew}>
            <Play /> New Investigation
          </Button>
        }
        className="py-8"
      />
    );
  }
  return (
    <ul className="divide-y divide-border">
      {items.map((i) => (
        <li key={i.id}>
          <Link href={`/investigations/${i.id}`} className="flex items-center gap-3 px-1 py-2 hover:bg-panel-2/60 rounded-md">
            <Mono className="text-fg-subtle">{i.display_id}</Mono>
            <span className="min-w-0 flex-1 truncate text-sm text-fg">{i.name}</span>
            <InvestigationStatusChip value={i.status} />
            <span className="hidden text-[11px] text-fg-subtle lg:inline">{formatRelative(i.updated_at)}</span>
            <ArrowRight className="size-3.5 text-fg-subtle" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function RecentFindings({ items }: { items: DashboardOut["recent_findings"] }) {
  if (items.length === 0) return <EmptyState title="No findings yet" description="Findings are drafted strictly from collected evidence." className="py-8" />;
  return (
    <ul className="divide-y divide-border">
      {items.map((f) => (
        <li key={f.id}>
          <Link href={`/findings/${f.id}`} className="flex items-center gap-3 rounded-md px-1 py-2 hover:bg-panel-2/60">
            <Mono className="text-fg-subtle">{f.display_id}</Mono>
            <span className="min-w-0 flex-1 truncate text-sm text-fg">{f.title}</span>
            <ConfidenceBadge value={f.confidence} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function LiveCollectionFeed({ items }: { items: DashboardOut["recent_events"] }) {
  if (items.length === 0) return <EmptyState title="No collection activity yet" description="Events from running investigations stream here." className="py-8" />;
  return (
    <ul className="max-h-80 space-y-0.5 overflow-y-auto font-mono text-xs">
      {items.map((e) => (
        <li key={e.id} className={cn("flex items-start gap-2 rounded px-1 py-1", e.level === "error" && "bg-danger/5", e.level === "warning" && "bg-warning/5")}>
          <span className="shrink-0 text-fg-subtle">{formatTime(e.created_at)}</span>
          <StageChip value={e.stage} />
          <Link href={`/investigations/${e.investigation_id}`} className={cn("min-w-0 flex-1 truncate font-sans text-fg-muted hover:text-fg", e.level === "error" && "text-danger", e.level === "warning" && "text-warning")}>
            {e.message}
          </Link>
        </li>
      ))}
    </ul>
  );
}
