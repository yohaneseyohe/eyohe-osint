"use client";

import { AlertTriangle } from "lucide-react";
import { useInvestigationStatus } from "@/lib/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/shared/states";
import { formatTs } from "@/lib/format";
import { Mono } from "@/components/shared/mono";

export function StatusPanel({ investigationId }: { investigationId: string }) {
  const q = useInvestigationStatus(investigationId);
  if (q.isPending) return <Skeleton className="h-64" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} compact />;
  const s = q.data;
  const counts = [
    ["Sources", s.sources_discovered],
    ["Entities", s.entities_discovered],
    ["Evidence", s.evidence_collected],
    ["Findings", s.findings],
  ] as const;
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Status summary</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            {counts.map(([l, n]) => (
              <div key={l} className="rounded-md border border-border bg-bg-elevated px-3 py-2">
                <div className="text-[10px] uppercase tracking-wider text-fg-subtle">{l}</div>
                <div className="font-mono text-lg text-fg">{n}</div>
              </div>
            ))}
          </div>
          <div>
            <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">Completeness by category</h4>
            {Object.keys(s.completeness).length === 0 ? <p className="text-xs text-fg-subtle">No enabled tasks.</p> : (
              <ul className="space-y-2">
                {Object.entries(s.completeness).map(([cat, pct]) => (
                  <li key={cat} className="text-xs">
                    <div className="mb-1 flex justify-between text-fg-muted"><span>{cat}</span><Mono>{pct}%</Mono></div>
                    <Progress value={pct} label={`${cat} completeness`} color={pct === 100 ? "bg-success" : "bg-accent"} />
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div><div className="text-[10px] uppercase tracking-wider text-fg-subtle">Started</div><Mono className="text-fg-muted">{s.started_at ? formatTs(s.started_at) : "—"}</Mono></div>
            <div><div className="text-[10px] uppercase tracking-wider text-fg-subtle">Finished</div><Mono className="text-fg-muted">{s.finished_at ? formatTs(s.finished_at) : "—"}</Mono></div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Remaining tasks ({s.remaining_tasks.length})</CardTitle></CardHeader>
        <CardContent>
          {s.remaining_tasks.length === 0 ? <p className="text-xs text-fg-subtle">Nothing pending.</p> : (
            <ul className="list-disc space-y-0.5 pl-4 text-xs text-fg-muted">{s.remaining_tasks.map((t) => <li key={t}>{t}</li>)}</ul>
          )}
        </CardContent>
      </Card>
      {s.warnings.length > 0 || s.errors.length > 0 ? (
        <Card className={s.errors.length > 0 ? "border-danger/30" : "border-warning/30"}>
          <CardHeader><CardTitle className="flex items-center gap-1.5"><AlertTriangle className="size-3.5" /> Warnings &amp; errors</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-xs">
            {s.errors.map((e, i) => <p key={`e${i}`} className="text-danger">{e}</p>)}
            {s.warnings.map((w, i) => <p key={`w${i}`} className="text-warning">{String(w)}</p>)}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
