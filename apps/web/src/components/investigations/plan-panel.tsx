"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Circle, Loader2, MinusCircle, SkipForward } from "lucide-react";
import { apiPatch, errorMessage } from "@/lib/api";
import { qk, useTaskCatalogue } from "@/lib/queries";
import type { InvestigationDetail, TaskOut } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { toast } from "@/components/ui/toast";
import { StageChip, TypeChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { cn } from "@/lib/utils";

function StatusIcon({ status, enabled }: { status: string; enabled: boolean }) {
  if (!enabled || status === "DISABLED") return <MinusCircle className="size-4 text-fg-subtle" aria-label="Disabled" />;
  switch (status) {
    case "RUNNING": return <Loader2 className="size-4 animate-spin text-accent-bright" aria-label="Running" />;
    case "COMPLETED": return <CheckCircle2 className="size-4 text-success" aria-label="Completed" />;
    case "FAILED": return <AlertCircle className="size-4 text-danger" aria-label="Failed" />;
    case "SKIPPED": return <SkipForward className="size-4 text-fg-subtle" aria-label="Skipped" />;
    default: return <Circle className="size-4 text-fg-subtle" aria-label="Pending" />;
  }
}

function ResultSummary({ r }: { r: Record<string, unknown> }) {
  const entries = Object.entries(r).filter(([, v]) => typeof v === "number" || typeof v === "string" || typeof v === "boolean");
  if (entries.length === 0) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {entries.slice(0, 8).map(([k, v]) => (
        <span key={k} className="rounded border border-border bg-bg-elevated px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
          {k}: <span className="text-fg">{String(v)}</span>
        </span>
      ))}
    </div>
  );
}

export function PlanPanel({ inv }: { inv: InvestigationDetail }) {
  const qc = useQueryClient();
  const catalogue = useTaskCatalogue();
  const editable = inv.status === "AWAITING_APPROVAL" || inv.status === "DRAFT";
  const toggle = useMutation({
    mutationFn: (t: { id: string; enabled: boolean }) => apiPatch<InvestigationDetail>(`/investigations/${inv.id}/plan`, { tasks: [t] }),
    onSuccess: (d) => qc.setQueryData(qk.investigation(inv.id), d),
    onError: (e) => toast.error("Could not update plan", errorMessage(e)),
  });
  const branches = inv.plan.branches ?? [];
  const byCategory = new Map<string, TaskOut[]>();
  for (const t of inv.tasks) byCategory.set(t.category, [...(byCategory.get(t.category) ?? []), t]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Plan <span className="font-mono text-[10px] normal-case tracking-normal text-fg-subtle">source: {inv.plan_source}</span>
        </CardTitle>
        <span className="text-xs text-fg-muted">{inv.tasks.filter((t) => t.enabled).length} of {inv.tasks.length} tasks enabled</span>
      </CardHeader>
      <CardContent className="space-y-4">
        {inv.plan_rationale ? <p className="rounded-md border border-border bg-bg-elevated px-3 py-2 text-xs text-fg-muted">{inv.plan_rationale}</p> : null}
        {inv.tasks.length === 0 ? <p className="text-xs text-fg-subtle">No tasks planned yet.</p> : null}
        {[...byCategory.entries()].map(([cat, tasks]) => (
          <section key={cat}>
            <h4 className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">{cat}</h4>
            <ol className="space-y-1.5">
              {tasks.map((t) => {
                const stage = catalogue.data?.[t.task_type]?.stage ?? t.task_type.toUpperCase();
                const taskBranches = Array.isArray(t.params.branches) ? (t.params.branches as string[]) : [];
                return (
                  <li key={t.id} className={cn("rounded-md border px-3 py-2", t.enabled ? "border-border bg-panel-2/40" : "border-border/50 opacity-60", t.status === "RUNNING" && "border-accent/50")}>
                    <div className="flex items-start gap-2.5">
                      <span className="mt-0.5"><StatusIcon status={t.status} enabled={t.enabled} /></span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium text-fg">{t.title}</span>
                          <StageChip value={stage} />
                          <TypeChip value={t.task_type} />
                          {t.attempts > 1 ? <span className="font-mono text-[10px] text-fg-subtle">attempt {t.attempts}</span> : null}
                        </div>
                        {t.rationale ? <p className="mt-1 text-xs text-fg-muted"><span className="text-fg-subtle">Why: </span>{t.rationale}</p> : null}
                        {taskBranches.length > 0 ? (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {taskBranches.map((b) => <Mono key={b} className="rounded bg-bg-elevated px-1.5 py-0.5 text-[10px] text-fg-muted">{b}</Mono>)}
                          </div>
                        ) : null}
                        {t.error ? <p className="mt-1 rounded border border-danger/30 bg-danger/5 px-2 py-1 text-xs text-danger">{t.error}</p> : null}
                        <ResultSummary r={t.result_summary} />
                      </div>
                      <Switch
                        checked={t.enabled}
                        disabled={!editable || toggle.isPending}
                        onCheckedChange={(enabled) => toggle.mutate({ id: t.id, enabled })}
                        aria-label={`${t.enabled ? "Disable" : "Enable"} task ${t.title}`}
                      />
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
        ))}
        {branches.length > 0 ? (
          <section>
            <h4 className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">Search branches</h4>
            <ul className="flex flex-wrap gap-1.5">
              {branches.map((b) => <li key={b}><Mono className="rounded border border-border bg-bg-elevated px-2 py-1 text-[11px] text-fg-muted">{b}</Mono></li>)}
            </ul>
          </section>
        ) : null}
      </CardContent>
    </Card>
  );
}
