"use client";

import Link from "next/link";
import { useEntity } from "@/lib/queries";
import { formatTs } from "@/lib/format";
import { Dialog, DialogBody, DialogContent } from "@/components/ui/dialog";
import { ConfidenceBadge, DemoBadge, ReviewChip, TypeChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { KeyValue, SectionTitle } from "@/components/shared/page-header";
import { ErrorState, LoadingState } from "@/components/shared/states";
import { EntityIcon } from "./entity-icon";
import { Button } from "@/components/ui/button";
import { Network } from "lucide-react";

export function EntityDrawer({ entityId, onClose }: { entityId: string | null; onClose: () => void }) {
  const query = useEntity(entityId);
  const d = query.data;
  return (
    <Dialog open={!!entityId} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        side="right"
        title={
          <span className="flex items-center gap-2">
            {d ? <EntityIcon type={d.entity.type} /> : null}
            <Mono>{d?.entity.value ?? "Entity"}</Mono>
            {d ? <TypeChip value={d.entity.type} /> : null}
            <DemoBadge show={d?.entity.is_demo} />
          </span>
        }
        description={d?.entity.display_id}
      >
        {query.isPending ? <div className="p-5"><LoadingState /></div> : null}
        {query.isError ? <div className="p-5"><ErrorState error={query.error} onRetry={() => query.refetch()} /></div> : null}
        {d ? (
          <DialogBody className="space-y-6">
            <dl className="grid grid-cols-2 gap-3 md:grid-cols-3">
              <KeyValue label="Confidence"><ConfidenceBadge value={d.entity.confidence} /></KeyValue>
              <KeyValue label="Sources" mono>{d.entity.source_count}</KeyValue>
              <KeyValue label="Target" mono>{d.entity.is_target ? "yes" : "no"}</KeyValue>
              <KeyValue label="First seen" mono>{formatTs(d.entity.first_seen)}</KeyValue>
              <KeyValue label="Last seen" mono>{formatTs(d.entity.last_seen)}</KeyValue>
              <KeyValue label="Normalized" mono>{d.entity.normalized_value}</KeyValue>
            </dl>
            {d.entity.label && d.entity.label !== d.entity.value ? <p className="text-sm text-fg-muted">{d.entity.label}</p> : null}
            <div className="flex gap-2">
              <Button asChild variant="outline" size="sm">
                <Link href={`/graph?case=${d.entity.case_id}&entity=${d.entity.id}`}>
                  <Network /> View in graph
                </Link>
              </Button>
            </div>

            <section className="space-y-2">
              <SectionTitle>Aliases</SectionTitle>
              {d.aliases.length === 0 ? (
                <p className="text-xs text-fg-subtle">No aliases recorded.</p>
              ) : (
                <ul className="flex flex-wrap gap-1.5">
                  {d.aliases.map((a, i) => (
                    <li key={i} className="rounded border border-border bg-panel-2 px-2 py-1 text-xs">
                      <Mono>{a.alias}</Mono> <span className="text-fg-subtle">{a.type}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="space-y-2">
              <SectionTitle>Relationships ({d.relationships.length})</SectionTitle>
              {d.relationships.length === 0 ? (
                <p className="text-xs text-fg-subtle">No relationships yet.</p>
              ) : (
                <ul className="divide-y divide-border rounded-md border border-border">
                  {d.relationships.map((r) => (
                    <li key={r.id} className="flex items-center gap-2 px-3 py-2 text-xs">
                      <Mono className="text-fg-subtle">{r.display_id}</Mono>
                      <TypeChip value={r.type} />
                      <span className="truncate text-fg-muted">{r.rationale || "—"}</span>
                      <ConfidenceBadge value={r.confidence} className="ml-auto" />
                      <ReviewChip value={r.review_state} />
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="space-y-2">
              <SectionTitle>Evidence ({d.evidence.length})</SectionTitle>
              {d.evidence.length === 0 ? (
                <p className="text-xs text-fg-subtle">No evidence linked.</p>
              ) : (
                <ul className="divide-y divide-border rounded-md border border-border">
                  {d.evidence.map((e) => (
                    <li key={e.id} className="px-3 py-2 text-xs">
                      <Link href={`/evidence?open=${e.id}`} className="flex items-center gap-2 hover:text-fg">
                        <Mono className="text-fg-subtle">{e.display_id}</Mono>
                        <span className="truncate text-fg-muted">{e.claim}</span>
                        <ConfidenceBadge value={e.confidence} className="ml-auto" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </DialogBody>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
