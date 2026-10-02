"use client";

import Link from "next/link";
import { format, parseISO } from "date-fns";
import { useTimeline } from "@/lib/queries";
import type { TimelineOut } from "@/lib/types";
import { formatWithPrecision } from "@/lib/format";
import { ConfidenceBadge, DemoBadge, TypeChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { EmptyState, QueryState } from "@/components/shared/states";

function groupKey(iso: string): string {
  try {
    return format(parseISO(iso), "yyyy · MMMM");
  } catch {
    return "Unknown";
  }
}

export function TimelineList({ caseId }: { caseId: string }) {
  const query = useTimeline(caseId);
  return (
    <QueryState query={query} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No timeline events yet" description="Dated events are extracted from evidence (publications, registrations, posts) as collection runs." />}>
      {(data) => {
        const sorted = [...data].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at));
        const groups = new Map<string, TimelineOut[]>();
        for (const e of sorted) groups.set(groupKey(e.occurred_at), [...(groups.get(groupKey(e.occurred_at)) ?? []), e]);
        return (
          <div className="relative pl-6">
            <div className="absolute left-2 top-0 h-full w-px bg-border" aria-hidden />
            {[...groups.entries()].map(([label, events]) => (
              <section key={label} className="mb-6">
                <h3 className="relative mb-3 text-xs font-semibold uppercase tracking-wider text-fg-muted">
                  <span className="absolute -left-6 top-1 size-2.5 rounded-full border-2 border-accent bg-bg" aria-hidden />
                  {label}
                </h3>
                <ol className="space-y-2">
                  {events.map((e) => (
                    <li key={e.id} className="glass relative rounded-lg border border-border px-4 py-3 animate-slide-in">
                      <span className="absolute -left-[1.15rem] top-4 size-1.5 rounded-full bg-fg-subtle" aria-hidden />
                      <div className="flex flex-wrap items-center gap-2">
                        <Mono className="text-fg-subtle">{formatWithPrecision(e.occurred_at, e.precision)}</Mono>
                        <span className="text-[10px] uppercase text-fg-subtle">{e.precision}</span>
                        <TypeChip value={e.event_kind} />
                        <ConfidenceBadge value={e.confidence} />
                        <DemoBadge show={e.is_demo} />
                      </div>
                      <p className="mt-1 text-sm text-fg">{e.title}</p>
                      {e.description ? <p className="mt-0.5 text-xs text-fg-muted">{e.description}</p> : null}
                      {e.evidence_id ? (
                        <Link href={`/evidence?open=${e.evidence_id}`} className="mt-1 inline-block text-xs text-accent-bright hover:underline">
                          View evidence
                        </Link>
                      ) : null}
                    </li>
                  ))}
                </ol>
              </section>
            ))}
          </div>
        );
      }}
    </QueryState>
  );
}
