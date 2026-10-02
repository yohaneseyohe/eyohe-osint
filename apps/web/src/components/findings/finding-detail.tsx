"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, HelpCircle } from "lucide-react";
import { apiPost, errorMessage } from "@/lib/api";
import { qk, useFinding } from "@/lib/queries";
import type { FindingDetail as FindingDetailT, FindingEvidenceRow, ReviewState } from "@/lib/types";
import { formatTs } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/toast";
import { ConfidenceBadge, DemoBadge, ReviewChip, TierBadge, TypeChip } from "@/components/shared/badges";
import { ExternalLink } from "@/components/shared/external-link";
import { Mono } from "@/components/shared/mono";
import { KeyValue, PageHeader } from "@/components/shared/page-header";
import { ReviewActions } from "@/components/shared/review-actions";
import { ErrorState, LoadingState } from "@/components/shared/states";
import { WhyPanel } from "./why-panel";
import { cn } from "@/lib/utils";

function EvidenceRows({ rows, tone }: { rows: FindingEvidenceRow[]; tone: "support" | "contradict" }) {
  if (rows.length === 0) return <p className="text-xs text-fg-subtle">None.</p>;
  return (
    <ul className="divide-y divide-border">
      {rows.map((e) => (
        <li key={e.id} className="py-2">
          <Link href={`/evidence?open=${e.id}`} className="block rounded-md px-1 py-1 hover:bg-panel-2/60">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Mono className={cn(tone === "contradict" ? "text-danger" : "text-fg-subtle")}>{e.display_id}</Mono>
              <TypeChip value={e.evidence_type} />
              <ConfidenceBadge value={e.confidence} />
              <ReviewChip value={e.review_state} />
              {e.source ? <TierBadge tier={e.source.tier} /> : null}
            </div>
            <p className="mt-1 text-sm text-fg">{e.claim}</p>
            {e.source ? (
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-fg-muted">
                <ExternalLink href={e.source.url} max={70} />
                <span>· collected <Mono>{formatTs(e.collected_at)}</Mono></span>
              </div>
            ) : null}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Body({ f }: { f: FindingDetailT }) {
  const [whyOpen, setWhyOpen] = useState(false);
  const qc = useQueryClient();
  const review = useMutation({
    mutationFn: (body: { state: ReviewState; note: string }) => apiPost<FindingDetailT>(`/findings/${f.id}/review`, body),
    onSuccess: (updated) => {
      qc.setQueryData(qk.finding(f.id), updated);
      qc.invalidateQueries({ queryKey: ["case", f.case_id, "findings"] });
      qc.invalidateQueries({ queryKey: qk.why(f.id) });
      toast.success(`Finding ${updated.display_id} marked ${updated.review_state.replace("_", " ").toLowerCase()}`);
    },
    onError: (e) => toast.error("Review failed", errorMessage(e)),
  });

  return (
    <div className="space-y-5">
      <PageHeader
        title={
          <>
            <Mono className="text-fg-subtle">{f.display_id}</Mono>
            {f.title}
            <DemoBadge show={f.is_demo} />
          </>
        }
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <Link href={`/cases/${f.case_id}?tab=findings`} className="inline-flex items-center gap-1 text-accent-bright hover:underline">
              <ArrowLeft className="size-3" /> Back to case findings
            </Link>
            <TypeChip value={f.category} />
            <span>severity {f.severity}</span>
            <span>· proposed by {f.proposed_by}</span>
          </span>
        }
        actions={
          <>
            <ConfidenceBadge value={f.confidence} className="text-xs" />
            <ReviewChip value={f.review_state} className="text-xs" />
            <Button onClick={() => setWhyOpen(true)}>
              <HelpCircle /> Why?
            </Button>
          </>
        }
      />
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <Card>
            <CardHeader><CardTitle>Claim</CardTitle></CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed text-fg">{f.claim}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Assessment</CardTitle></CardHeader>
            <CardContent>
              {f.assessment ? <p className="text-sm leading-relaxed text-fg-muted whitespace-pre-wrap">{f.assessment}</p> : <p className="text-xs text-fg-subtle">No assessment written.</p>}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Supporting evidence ({f.supporting.length})</CardTitle></CardHeader>
            <CardContent className="py-2"><EvidenceRows rows={f.supporting} tone="support" /></CardContent>
          </Card>
          <Card className={f.contradicting.length > 0 ? "border-danger/30" : undefined}>
            <CardHeader><CardTitle className={f.contradicting.length > 0 ? "text-danger" : undefined}>Contradicting evidence ({f.contradicting.length})</CardTitle></CardHeader>
            <CardContent className="py-2"><EvidenceRows rows={f.contradicting} tone="contradict" /></CardContent>
          </Card>
        </div>
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Details</CardTitle></CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-3">
                <KeyValue label="Created" mono>{formatTs(f.created_at)}</KeyValue>
                <KeyValue label="Updated" mono>{formatTs(f.updated_at)}</KeyValue>
                <KeyValue label="Entities" mono>{f.entity_ids.length}</KeyValue>
                <KeyValue label="Relationships" mono>{f.relationship_ids.length}</KeyValue>
                <KeyValue label="Investigation" mono>{f.investigation_id ? <Link className="text-accent-bright hover:underline" href={`/investigations/${f.investigation_id}`}>{f.investigation_id.slice(0, 8)}</Link> : "—"}</KeyValue>
              </dl>
            </CardContent>
          </Card>
          {f.confidence_rationale?.reasons && f.confidence_rationale.reasons.length > 0 ? (
            <Card>
              <CardHeader><CardTitle>Confidence rationale</CardTitle></CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1 pl-4 text-xs text-fg">
                  {f.confidence_rationale.reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
          <Card>
            <CardHeader><CardTitle>Analyst review</CardTitle></CardHeader>
            <CardContent>
              {f.review_note ? <p className="mb-3 text-xs text-fg-muted">Last note: {f.review_note}</p> : null}
              <ReviewActions current={f.review_state} pending={review.isPending} onReview={(state, note) => review.mutate({ state, note })} />
            </CardContent>
          </Card>
        </div>
      </div>
      <WhyPanel findingId={f.id} open={whyOpen} onOpenChange={setWhyOpen} />
    </div>
  );
}

export function FindingDetailView({ id }: { id: string }) {
  const query = useFinding(id);
  if (query.isPending) return <LoadingState rows={8} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  return <Body f={query.data} />;
}
