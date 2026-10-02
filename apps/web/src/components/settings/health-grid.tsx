"use client";

import { RefreshCw } from "lucide-react";
import { useHealth } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { HealthChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { ErrorState } from "@/components/shared/states";

export function HealthGrid() {
  const health = useHealth(30_000);
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-fg-muted">
          {health.data ? (
            <>
              <HealthChip value={health.data.status} />
              <span>v{health.data.version} · {health.data.environment} · jobs: {health.data.job_backend} · graph: {health.data.graph_backend}</span>
            </>
          ) : null}
        </div>
        <Button variant="outline" size="xs" onClick={() => health.refetch()} loading={health.isFetching}><RefreshCw /> Re-check</Button>
      </div>
      {health.isPending ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div> : null}
      {health.isError ? <ErrorState error={health.error} onRetry={() => health.refetch()} /> : null}
      {health.data ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {health.data.components.map((c) => {
            const detailEntries = Object.entries(c.detail).filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && v.length === 0));
            return (
              <Card key={c.name}>
                <CardHeader className="py-2">
                  <CardTitle className="capitalize">{c.name}{c.optional ? <span className="ml-1 text-[9px] text-fg-subtle">optional</span> : null}</CardTitle>
                  <HealthChip value={c.status} />
                </CardHeader>
                <CardContent className="space-y-1.5 py-3 text-xs">
                  <p className="text-fg-muted">{c.message || "—"}</p>
                  {c.latency_ms != null ? <p className="text-fg-subtle">latency <Mono>{c.latency_ms} ms</Mono></p> : null}
                  {detailEntries.map(([k, v]) => (
                    <p key={k} className="truncate text-fg-subtle" title={typeof v === "string" ? v : JSON.stringify(v)}>
                      {k}: <Mono className="text-fg-muted">{Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : String(v)}</Mono>
                    </p>
                  ))}
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
