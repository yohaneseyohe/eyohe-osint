"use client";

import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useCase, useInvestigation, useInvestigationStatus } from "@/lib/queries";
import { Progress } from "@/components/ui/progress";
import { DemoBadge, InvestigationStatusChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorState, LoadingState } from "@/components/shared/states";
import { InvestigationControls } from "./controls";
import { LiveFeed } from "./live-feed";
import { PlanPanel } from "./plan-panel";
import { StatusPanel } from "./status-panel";

const LIVE = new Set(["PLANNING", "RUNNING", "VERIFYING", "PAUSED", "AWAITING_APPROVAL"]);

export function InvestigationDetailView({ id }: { id: string }) {
  const query = useInvestigation(id);
  const status = useInvestigationStatus(id);
  const kase = useCase(query.data?.case_id ?? null);
  if (query.isPending) return <LoadingState rows={8} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  const inv = query.data;
  const progress = status.data?.progress ?? 0;

  return (
    <div className="space-y-4">
      <PageHeader
        title={<><Mono className="text-fg-subtle">{inv.display_id}</Mono>{inv.name || inv.request_text || "Investigation"}<InvestigationStatusChip value={inv.status} /><DemoBadge show={kase.data?.is_demo} /></>}
        subtitle={
          <span className="flex flex-wrap items-center gap-3">
            <Link href={`/cases/${inv.case_id}`} className="inline-flex items-center gap-1 text-accent-bright hover:underline"><ArrowLeft className="size-3" /> {kase.data ? `${kase.data.display_id} · ${kase.data.name}` : "Case"}</Link>
            {inv.objective ? <span>{inv.objective}</span> : null}
          </span>
        }
        actions={<InvestigationControls inv={inv} />}
      >
        <div className="flex items-center gap-3">
          <Progress value={progress} label="Investigation progress" className="h-2" color={inv.status === "FAILED" ? "bg-danger" : inv.status === "COMPLETED" ? "bg-success" : "bg-accent"} />
          <Mono className="w-10 text-right text-xs text-fg-muted">{progress}%</Mono>
        </div>
        {inv.error ? <p className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">{inv.error}</p> : null}
        {inv.status === "PLANNING" ? (
          <p className="flex items-center gap-2 rounded-md border border-violet/30 bg-violet/5 px-3 py-2 text-xs text-violet">
            <Loader2 className="size-3.5 animate-spin" /> Planning… the local model is adapting the task plan to your objective (this can take minutes on CPU). The feed shows its progress; the plan appears here for approval when it is ready.
          </p>
        ) : null}
        {inv.status === "AWAITING_APPROVAL" ? <p className="rounded-md border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">Review the plan below. Toggle tasks you do not want, then approve to start collection.</p> : null}
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_20rem] 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_22rem]">
        <PlanPanel inv={inv} />
        <LiveFeed investigationId={inv.id} live={LIVE.has(inv.status)} />
        <div className="lg:col-span-2 xl:col-span-1"><StatusPanel investigationId={inv.id} /></div>
      </div>
    </div>
  );
}
