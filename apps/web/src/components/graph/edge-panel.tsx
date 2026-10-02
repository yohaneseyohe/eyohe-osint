"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { apiPost, errorMessage } from "@/lib/api";
import { qk, useRelationship } from "@/lib/queries";
import type { RelationshipDetail, ReviewState } from "@/lib/types";
import { formatTs } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { ConfidenceBadge, DemoBadge, ReviewChip, TypeChip } from "@/components/shared/badges";
import { ExternalLink } from "@/components/shared/external-link";
import { Mono } from "@/components/shared/mono";
import { SectionTitle } from "@/components/shared/page-header";
import { ReviewActions } from "@/components/shared/review-actions";
import { ErrorState, LoadingState } from "@/components/shared/states";
import { ConfidenceReasons } from "@/components/findings/why-panel";

function Body({ rel, caseId }: { rel: RelationshipDetail; caseId: string }) {
  const qc = useQueryClient();
  const review = useMutation({
    mutationFn: (body: { state: ReviewState; note: string }) => apiPost<RelationshipDetail>(`/relationships/${rel.id}/review`, body),
    onSuccess: (updated) => {
      qc.setQueryData(qk.relationship(rel.id), updated);
      qc.invalidateQueries({ queryKey: ["case", caseId, "graph"] });
      toast.success(`Relationship ${updated.display_id} marked ${updated.review_state.replace("_", " ").toLowerCase()}`);
    },
    onError: (e) => toast.error("Review failed", errorMessage(e)),
  });
  const why = rel.why;
  return (
    <div className="space-y-5 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Mono className="text-fg-subtle">{rel.display_id}</Mono>
        <TypeChip value={rel.type} />
        <ConfidenceBadge value={rel.confidence} />
        <ReviewChip value={rel.review_state} />
        <DemoBadge show={rel.is_demo} />
      </div>
      <div className="rounded-md border border-border bg-bg-elevated p-3 text-sm">
        <Mono className="text-fg">{rel.source_entity?.value ?? rel.source_entity_id}</Mono>
        <span className="mx-2 text-accent-bright">—{rel.type}→</span>
        <Mono className="text-fg">{rel.target_entity?.value ?? rel.target_entity_id}</Mono>
      </div>
      <section className="space-y-2">
        <SectionTitle>Why does this relationship exist?</SectionTitle>
        {why?.question ? <p className="text-xs italic text-fg-muted">{why.question}</p> : null}
        <p className="text-sm text-fg">{rel.rationale || "No rationale recorded."}</p>
      </section>
      <section className="space-y-2">
        <SectionTitle>Evidence chain ({why?.chain?.length ?? 0})</SectionTitle>
        {!why || why.chain.length === 0 ? (
          <p className="text-xs text-warning">No evidence is linked to this relationship.</p>
        ) : (
          <ol className="space-y-2">
            {why.chain.map((s, i) => (
              <li key={`${s.evidence_id}-${i}`} className="rounded-md border border-border bg-panel-2/40 px-3 py-2 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <Mono className="text-fg">{s.evidence_id}</Mono>
                  <span className={s.role === "contradicts" ? "text-danger uppercase text-[10px]" : "text-success uppercase text-[10px]"}>{s.role}</span>
                  <span className="ml-auto text-fg-subtle">{s.collector}</span>
                </div>
                <p className="mt-1 text-sm text-fg">{s.claim}</p>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-fg-muted">
                  {s.source_url ? <ExternalLink href={s.source_url} max={60} /> : <span className="text-fg-subtle">no source URL</span>}
                  <span>· <Mono>{formatTs(s.collected_at)}</Mono></span>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
      {why?.confidence ? (
        <section className="space-y-2">
          <SectionTitle>Confidence reasons</SectionTitle>
          <ConfidenceReasons c={why.confidence} />
        </section>
      ) : null}
      <section className="space-y-2">
        <SectionTitle>Review</SectionTitle>
        {rel.review_note ? <p className="text-xs text-fg-muted">Last note: {rel.review_note}</p> : null}
        <ReviewActions
          current={rel.review_state}
          pending={review.isPending}
          onReview={(state, note) => review.mutate({ state, note })}
          labels={{ accept: "Confirm", reject: "Reject", verify: "Mark unverified" }}
        />
      </section>
    </div>
  );
}

export function EdgePanel({ relationshipId, caseId, onClose }: { relationshipId: string; caseId: string; onClose: () => void }) {
  const query = useRelationship(relationshipId);
  return (
    <aside className="flex h-full w-96 shrink-0 flex-col border-l border-border bg-panel" aria-label="Relationship details">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-fg">Relationship</h3>
        <Button variant="ghost" size="icon-xs" onClick={onClose} aria-label="Close panel"><X /></Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {query.isPending ? <div className="p-4"><LoadingState /></div> : null}
        {query.isError ? <div className="p-4"><ErrorState error={query.error} onRetry={() => query.refetch()} /></div> : null}
        {query.data ? <Body rel={query.data} caseId={caseId} /> : null}
      </div>
    </aside>
  );
}
