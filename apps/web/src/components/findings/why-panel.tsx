"use client";

import { BadgeCheck, FileWarning } from "lucide-react";
import { useWhy } from "@/lib/queries";
import type { ConfidenceRationale, WhyChainStep } from "@/lib/types";
import { formatTs } from "@/lib/format";
import { Dialog, DialogBody, DialogContent } from "@/components/ui/dialog";
import { ConfidenceBadge, ReviewChip, TierBadge, TypeChip } from "@/components/shared/badges";
import { ExternalLink } from "@/components/shared/external-link";
import { Mono } from "@/components/shared/mono";
import { SectionTitle } from "@/components/shared/page-header";
import { ErrorState, LoadingState } from "@/components/shared/states";
import { cn } from "@/lib/utils";

export function ConfidenceReasons({ c }: { c: ConfidenceRationale }) {
  return (
    <div className="space-y-2 rounded-md border border-border bg-bg-elevated p-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
        <ConfidenceBadge value={c.label} />
        <span>{c.independent_sources} independent source{c.independent_sources === 1 ? "" : "s"}</span>
        {c.best_tier != null ? <>· best <TierBadge tier={c.best_tier} /></> : null}
        {c.source_quality ? <>· {c.source_quality}</> : null}
      </div>
      {c.reasons.length > 0 ? (
        <ul className="list-disc space-y-1 pl-4 text-xs text-fg">
          {c.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-fg-subtle">No reasons recorded.</p>
      )}
    </div>
  );
}

function ChainStep({ step }: { step: WhyChainStep }) {
  const contradicts = step.role === "contradicts";
  return (
    <li className={cn("relative rounded-lg border px-4 py-3", contradicts ? "border-danger/40 bg-danger/5" : "border-border bg-panel-2/40")}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="flex size-5 items-center justify-center rounded-full bg-accent-soft font-mono text-[10px] text-accent-bright">{step.step}</span>
        <Mono className="text-fg">{step.evidence_id}</Mono>
        <TypeChip value={step.evidence_type} />
        <span className={cn("font-medium uppercase text-[10px]", contradicts ? "text-danger" : "text-success")}>{step.role}</span>
        <ReviewChip value={step.review_state} className="ml-auto" />
      </div>
      <p className="mt-2 text-sm text-fg">{step.claim}</p>
      {step.excerpt ? <blockquote className="mt-2 border-l-2 border-border-strong pl-2 font-mono text-[11px] text-fg-muted line-clamp-4">{step.excerpt}</blockquote> : null}
      <div className="mt-2 grid gap-1 text-xs text-fg-muted">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-fg-subtle">source →</span>
          {step.source ? (
            <>
              <TierBadge tier={step.source.tier} />
              <Mono className="text-fg-subtle">{step.source.display_id}</Mono>
              <span className="truncate">{step.source.title || step.source.domain}</span>
            </>
          ) : (
            <span>collector {step.collector}</span>
          )}
        </div>
        {step.source ? (
          <div className="flex items-center gap-2">
            <span className="text-fg-subtle">url →</span>
            <ExternalLink href={step.source.url} max={90} />
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-fg-subtle">collected →</span>
          <Mono>{formatTs(step.collected_at)}</Mono>
          <span className="text-fg-subtle">·</span>
          {step.excerpt_verified ? (
            <span className="inline-flex items-center gap-1 text-success"><BadgeCheck className="size-3.5" /> verified excerpt</span>
          ) : (
            <span className="inline-flex items-center gap-1 text-warning"><FileWarning className="size-3.5" /> unverified excerpt</span>
          )}
        </div>
      </div>
    </li>
  );
}

export function WhyPanel({ findingId, open, onOpenChange }: { findingId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const why = useWhy(findingId, open);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent side="right" className="max-w-3xl" title="Why does this finding exist?" description="The complete evidence chain and the computed confidence rationale. Nothing here is generated without a cited source.">
        {why.isPending ? <div className="p-5"><LoadingState rows={8} /></div> : null}
        {why.isError ? <div className="p-5"><ErrorState error={why.error} onRetry={() => why.refetch()} /></div> : null}
        {why.data ? (
          <DialogBody className="space-y-6">
            <section className="space-y-2">
              <SectionTitle>Finding</SectionTitle>
              <p className="text-sm font-medium text-fg">{why.data.finding.title}</p>
              <p className="text-sm text-fg-muted">{why.data.finding.claim}</p>
            </section>
            <section className="space-y-2">
              <SectionTitle>Evidence chain ({why.data.chain.length})</SectionTitle>
              {why.data.chain.length === 0 ? (
                <p className="text-xs text-warning">This finding cites no evidence. It should not be accepted until evidence is attached.</p>
              ) : (
                <ol className="space-y-2">
                  {why.data.chain.map((s) => (
                    <ChainStep key={s.step} step={s} />
                  ))}
                </ol>
              )}
            </section>
            <section className="space-y-2">
              <SectionTitle>Computed reasoning</SectionTitle>
              <p className="rounded-md border border-border bg-bg-elevated p-3 text-sm leading-relaxed text-fg">{why.data.reasoning || "No reasoning text was produced."}</p>
            </section>
            <section className="space-y-2">
              <SectionTitle>Confidence</SectionTitle>
              <ConfidenceReasons c={why.data.confidence} />
            </section>
          </DialogBody>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
