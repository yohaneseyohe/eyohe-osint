"use client";

import Link from "next/link";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { useInvestigationStatus, useInvestigations } from "@/lib/queries";
import type { CaseDetail } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { InvestigationStatusChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { EmptyState } from "@/components/shared/states";
import { Skeleton } from "@/components/ui/skeleton";

import { AskPanel } from "@/components/ai/ask-panel";

/** Run state on the left, evidence-only Q&A on the right. */
export function AiAnalystPanel({ c, initialQuestion }: { c: CaseDetail; initialQuestion?: string }) {
  const invs = useInvestigations({ case_id: c.id });
  const latest = invs.data ? [...invs.data].sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0] : undefined;
  const status = useInvestigationStatus(latest?.id ?? null);
  const s = status.data;

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        <Card>
          <CardHeader><CardTitle>Objective</CardTitle></CardHeader>
          <CardContent><p className="text-sm text-fg">{c.objective || <span className="text-fg-subtle">No objective set for this case.</span>}</p></CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Latest investigation</CardTitle>
            {latest ? <Link href={`/investigations/${latest.id}`} className="text-xs text-accent-bright hover:underline">Open run</Link> : null}
          </CardHeader>
          <CardContent>
            {invs.isPending ? <Skeleton className="h-16" /> : null}
            {!invs.isPending && !latest ? <EmptyState title="No investigations yet — start one" className="py-6" /> : null}
            {latest && s ? (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Mono className="text-fg-subtle">{s.display_id}</Mono>
                  <InvestigationStatusChip value={s.status} />
                  <span className="text-xs text-fg-muted">plan: {s.plan_source}</span>
                  <span className="ml-auto font-mono text-xs text-fg">{s.progress}%</span>
                </div>
                <Progress value={s.progress} label="Investigation progress" />
                {s.active_task ? <p className="flex items-center gap-2 text-xs text-fg-muted"><Loader2 className="size-3.5 animate-spin text-accent-bright" /> Running: {s.active_task.title}</p> : null}
                <ul className="space-y-1 text-xs">
                  {s.completed_tasks.map((t) => <li key={`d-${t}`} className="flex items-center gap-2 text-fg-muted"><CheckCircle2 className="size-3.5 text-success" /> {t}</li>)}
                  {s.failed_tasks.map((t) => <li key={`f-${t.title}`} className="flex items-center gap-2 text-danger"><Circle className="size-3.5" /> {t.title}{t.error ? ` — ${t.error}` : ""}</li>)}
                  {s.remaining_tasks.map((t) => <li key={`r-${t}`} className="flex items-center gap-2 text-fg-subtle"><Circle className="size-3.5" /> {t}</li>)}
                </ul>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
      <div className="self-start"><AskPanel key={initialQuestion ?? ""} caseId={c.id} initialQuestion={initialQuestion} /></div>
    </div>
  );
}
