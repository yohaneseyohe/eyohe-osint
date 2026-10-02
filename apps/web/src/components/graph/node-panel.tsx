"use client";

import Link from "next/link";
import { Expand, X } from "lucide-react";
import { useEntity } from "@/lib/queries";
import { formatTs } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { ConfidenceBadge, DemoBadge, ReviewChip, TypeChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { KeyValue, SectionTitle } from "@/components/shared/page-header";
import { ErrorState, LoadingState } from "@/components/shared/states";
import { EntityIcon } from "@/components/entities/entity-icon";

export function NodePanel({ entityId, onClose, onExpand, onSelectEdge }: { entityId: string; onClose: () => void; onExpand: (id: string) => void; onSelectEdge: (relId: string) => void }) {
  const query = useEntity(entityId);
  const d = query.data;
  return (
    <aside className="flex h-full w-96 shrink-0 flex-col border-l border-border bg-panel" aria-label="Entity details">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-fg">
          {d ? <EntityIcon type={d.entity.type} /> : null} Entity
        </h3>
        <Button variant="ghost" size="icon-xs" onClick={onClose} aria-label="Close panel"><X /></Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {query.isPending ? <div className="p-4"><LoadingState /></div> : null}
        {query.isError ? <div className="p-4"><ErrorState error={query.error} onRetry={() => query.refetch()} /></div> : null}
        {d ? (
          <div className="space-y-5 p-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <TypeChip value={d.entity.type} />
                <ConfidenceBadge value={d.entity.confidence} />
                <DemoBadge show={d.entity.is_demo} />
                {d.entity.is_target ? <span className="text-[10px] uppercase text-accent-bright">target</span> : null}
              </div>
              <Mono className="mt-2 block break-all text-base text-fg">{d.entity.value}</Mono>
              {d.entity.label && d.entity.label !== d.entity.value ? <p className="text-xs text-fg-muted">{d.entity.label}</p> : null}
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => onExpand(d.entity.id)}><Expand /> Expand neighbourhood</Button>
              <Button asChild variant="outline" size="sm"><Link href={`/entities`}>All entities</Link></Button>
            </div>
            <dl className="grid grid-cols-2 gap-3">
              <KeyValue label="ID" mono>{d.entity.display_id}</KeyValue>
              <KeyValue label="Sources" mono>{d.entity.source_count}</KeyValue>
              <KeyValue label="First seen" mono>{formatTs(d.entity.first_seen)}</KeyValue>
              <KeyValue label="Last seen" mono>{formatTs(d.entity.last_seen)}</KeyValue>
            </dl>
            {d.aliases.length > 0 ? (
              <section className="space-y-1.5">
                <SectionTitle>Aliases</SectionTitle>
                <ul className="flex flex-wrap gap-1.5">
                  {d.aliases.map((a, i) => <li key={i} className="rounded border border-border bg-panel-2 px-2 py-0.5 text-xs"><Mono>{a.alias}</Mono></li>)}
                </ul>
              </section>
            ) : null}
            <section className="space-y-1.5">
              <SectionTitle>Relationships ({d.relationships.length})</SectionTitle>
              {d.relationships.length === 0 ? <p className="text-xs text-fg-subtle">None.</p> : (
                <ul className="divide-y divide-border rounded-md border border-border">
                  {d.relationships.map((r) => (
                    <li key={r.id}>
                      <button onClick={() => onSelectEdge(r.id)} className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-xs hover:bg-panel-2">
                        <TypeChip value={r.type} />
                        <span className="truncate text-fg-muted">{r.rationale || r.display_id}</span>
                        <ConfidenceBadge value={r.confidence} className="ml-auto" />
                        <ReviewChip value={r.review_state} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="space-y-1.5">
              <SectionTitle>Evidence ({d.evidence.length})</SectionTitle>
              {d.evidence.length === 0 ? <p className="text-xs text-fg-subtle">None linked.</p> : (
                <ul className="space-y-1">
                  {d.evidence.slice(0, 20).map((e) => (
                    <li key={e.id} className="text-xs">
                      <Link href={`/evidence?open=${e.id}`} className="flex items-center gap-2 rounded px-1 py-0.5 hover:bg-panel-2">
                        <Mono className="text-fg-subtle">{e.display_id}</Mono>
                        <span className="truncate text-fg-muted">{e.claim}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        ) : null}
      </div>
    </aside>
  );
}
