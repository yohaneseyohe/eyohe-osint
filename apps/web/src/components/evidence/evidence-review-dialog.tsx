"use client";

import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, FileWarning } from "lucide-react";
import { apiPost, errorMessage } from "@/lib/api";
import { qk, useEvidence } from "@/lib/queries";
import type { EvidenceDetail, ReviewState } from "@/lib/types";
import { formatBytes, formatTs } from "@/lib/format";
import { Dialog, DialogBody, DialogContent } from "@/components/ui/dialog";
import { toast } from "@/components/ui/toast";
import { ConfidenceBadge, DemoBadge, ReviewChip, TierBadge, TypeChip } from "@/components/shared/badges";
import { ExternalLink } from "@/components/shared/external-link";
import { Mono } from "@/components/shared/mono";
import { KeyValue, SectionTitle } from "@/components/shared/page-header";
import { ReviewActions } from "@/components/shared/review-actions";
import { ErrorState, LoadingState } from "@/components/shared/states";
import { TIER_LABELS } from "@/lib/labels";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <SectionTitle>{title}</SectionTitle>
      {children}
    </section>
  );
}

function ReviewBody({ ev }: { ev: EvidenceDetail }) {
  const qc = useQueryClient();
  const review = useMutation({
    mutationFn: (body: { state: ReviewState; note: string }) => apiPost<EvidenceDetail>(`/evidence/${ev.id}/review`, body),
    onSuccess: (updated) => {
      qc.setQueryData(qk.evidence(ev.id), updated);
      qc.invalidateQueries({ queryKey: ["case", ev.case_id, "evidence"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(`Evidence ${updated.display_id} marked ${updated.review_state.replace("_", " ").toLowerCase()}`);
    },
    onError: (e) => toast.error("Review failed", errorMessage(e)),
  });

  const structuredUrl = typeof ev.structured.url === "string" ? ev.structured.url : null;
  const url = ev.source?.url ?? structuredUrl;

  return (
    <DialogBody className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <TypeChip value={ev.evidence_type} />
        <ConfidenceBadge value={ev.confidence} />
        <ReviewChip value={ev.review_state} />
        <DemoBadge show={ev.is_demo} />
        {ev.redacted ? <span className="text-[11px] text-warning">redacted</span> : null}
      </div>

      <Section title="Source">
        {ev.source ? (
          <div className="space-y-1.5 rounded-md border border-border bg-bg-elevated p-3">
            <div className="flex flex-wrap items-center gap-2">
              <TierBadge tier={ev.source.tier} verbose />
              <Mono className="text-fg-subtle">{ev.source.display_id}</Mono>
              <TypeChip value={ev.source.source_type} />
            </div>
            <p className="text-sm text-fg">{ev.source.title || ev.source.domain}</p>
            <ExternalLink href={ev.source.url} max={110} />
            {ev.source.reliability_note ? <p className="text-xs text-fg-muted">{ev.source.reliability_note}</p> : null}
          </div>
        ) : url ? (
          <ExternalLink href={url} max={110} />
        ) : (
          <p className="text-xs text-fg-subtle">No source record attached (collector: {ev.collector || "unknown"}).</p>
        )}
      </Section>

      <Section title="Claim">
        <p className="text-sm leading-relaxed text-fg">{ev.claim}</p>
      </Section>

      <Section title="Excerpt">
        {ev.excerpt ? (
          <blockquote className="rounded-md border-l-2 border-accent/60 bg-accent-soft/40 px-3 py-2 font-mono text-xs leading-relaxed text-fg-muted whitespace-pre-wrap">
            {ev.excerpt}
          </blockquote>
        ) : (
          <p className="text-xs text-fg-subtle">No excerpt captured.</p>
        )}
        <p className="flex items-center gap-1.5 text-xs">
          {ev.excerpt_verified ? (
            <>
              <BadgeCheck className="size-3.5 text-success" /> <span className="text-success">Excerpt verified in snapshot</span>
            </>
          ) : (
            <>
              <FileWarning className="size-3.5 text-warning" /> <span className="text-warning">Excerpt not verified against a snapshot</span>
            </>
          )}
        </p>
      </Section>

      {ev.context ? (
        <Section title="Context">
          <p className="text-sm text-fg-muted">{ev.context}</p>
        </Section>
      ) : null}

      <Section title="Collected">
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-3">
          <KeyValue label="Collector" mono>{ev.collector || "—"}</KeyValue>
          <KeyValue label="Method" mono>{ev.collection_method || "—"}</KeyValue>
          <KeyValue label="Collected at" mono>{formatTs(ev.collected_at)}</KeyValue>
          <KeyValue label="Observed at" mono>{ev.observed_at ? formatTs(ev.observed_at) : "—"}</KeyValue>
          <KeyValue label="Content hash" mono>{ev.content_hash ? ev.content_hash.slice(0, 16) + "…" : "—"}</KeyValue>
          <KeyValue label="Investigation" mono>{ev.investigation_id ? <Link className="text-accent-bright hover:underline" href={`/investigations/${ev.investigation_id}`}>{ev.investigation_id.slice(0, 8)}</Link> : "—"}</KeyValue>
        </dl>
      </Section>

      <Section title="Source quality">
        {ev.source ? (
          <p className="text-sm text-fg-muted">
            Tier {ev.source.tier} — {TIER_LABELS[ev.source.tier] ?? "unknown"}. Domain <Mono>{ev.source.domain}</Mono>
            {ev.source.publisher ? <> · publisher {ev.source.publisher}</> : null}.
          </p>
        ) : (
          <p className="text-xs text-fg-subtle">Quality cannot be assessed without a linked source.</p>
        )}
      </Section>

      <Section title="Related entities">
        {ev.entities.length === 0 ? (
          <p className="text-xs text-fg-subtle">None linked.</p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {ev.entities.map((en, i) => (
              <li key={en.id ?? i} className="flex items-center gap-1.5 rounded border border-border bg-panel-2 px-2 py-1 text-xs">
                {en.type ? <TypeChip value={en.type} /> : null}
                <Mono>{en.value ?? en.label ?? "?"}</Mono>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Related findings">
        {ev.findings.length === 0 ? (
          <p className="text-xs text-fg-subtle">Not cited by any finding yet.</p>
        ) : (
          <ul className="space-y-1">
            {ev.findings.map((f, i) => (
              <li key={f.id ?? i}>
                {f.id ? (
                  <Link href={`/findings/${f.id}`} className="flex items-center gap-2 text-sm text-accent-bright hover:underline">
                    <Mono className="text-fg-subtle">{f.display_id}</Mono> {f.title}
                  </Link>
                ) : (
                  <span className="text-sm">{f.title}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Artifacts">
        {ev.artifacts.length === 0 ? (
          <p className="text-xs text-fg-subtle">No stored artifacts.</p>
        ) : (
          <ul className="divide-y divide-border rounded-md border border-border">
            {ev.artifacts.map((a) => (
              <li key={a.id} className="flex items-center gap-3 px-3 py-2 text-xs">
                <TypeChip value={a.kind} />
                <a className="text-accent-bright hover:underline" href={`/api/v1/evidence/${ev.id}/artifacts/${a.id}`} target="_blank" rel="noopener noreferrer">
                  <Mono>{a.path.split("/").pop()}</Mono>
                </a>
                <span className="text-fg-subtle">{a.mime_type}</span>
                <span className="ml-auto font-mono text-fg-subtle">{formatBytes(a.size_bytes)}</span>
                <Mono className="text-fg-subtle" title={a.sha256}>{a.sha256.slice(0, 12)}</Mono>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Review">
        {ev.review_note ? (
          <p className="text-xs text-fg-muted">
            Last note{ev.reviewed_at ? <> ({formatTs(ev.reviewed_at)})</> : null}: {ev.review_note}
          </p>
        ) : null}
        <ReviewActions current={ev.review_state} pending={review.isPending} onReview={(state, note) => review.mutate({ state, note })} />
      </Section>
    </DialogBody>
  );
}

export function EvidenceReviewDialog({ evidenceId, onClose }: { evidenceId: string | null; onClose: () => void }) {
  const query = useEvidence(evidenceId);
  return (
    <Dialog open={!!evidenceId} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        side="right"
        title={
          <span className="flex items-center gap-2">
            Evidence Review <Mono className="text-fg-subtle">{query.data?.display_id ?? ""}</Mono>
          </span>
        }
        description="Source → claim → excerpt → context. Every decision is recorded in the audit log."
      >
        {query.isPending ? <div className="p-5"><LoadingState rows={8} /></div> : null}
        {query.isError ? <div className="p-5"><ErrorState error={query.error} onRetry={() => query.refetch()} /></div> : null}
        {query.data ? <ReviewBody ev={query.data} /> : null}
      </DialogContent>
    </Dialog>
  );
}
