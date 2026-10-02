"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, CheckCheck } from "lucide-react";
import { apiPost, errorMessage } from "@/lib/api";
import { useAlerts } from "@/lib/queries";
import type { AlertOut } from "@/lib/types";
import { formatTs } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "@/components/ui/toast";
import { Mono } from "@/components/shared/mono";
import { TypeChip } from "@/components/shared/badges";
import { Pagination } from "@/components/shared/pagination";
import { EmptyState, QueryState } from "@/components/shared/states";
import { cn } from "@/lib/utils";

const SEVERITY: Record<string, string> = { CRITICAL: "border-danger/50 text-danger", HIGH: "border-danger/40 text-danger", MEDIUM: "border-warning/40 text-warning", LOW: "border-border text-fg-muted", INFO: "border-border text-fg-muted" };
const PAGE_SIZE = 50;

export function useAlertActions() {
  const qc = useQueryClient();
  const refresh = () => { qc.invalidateQueries({ queryKey: ["alerts"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); };
  const ack = useMutation({
    mutationFn: (id: string) => apiPost<AlertOut>(`/alerts/${id}/ack`),
    onSuccess: refresh,
    onError: (e) => toast.error("Could not acknowledge", errorMessage(e)),
  });
  const readAll = useMutation({
    mutationFn: (caseId?: string | null) => apiPost<{ updated: number }>(`/alerts/read-all${caseId ? `?case_id=${caseId}` : ""}`),
    onSuccess: (r) => { refresh(); toast.success(`${r.updated} alert${r.updated === 1 ? "" : "s"} marked read`); },
    onError: (e) => toast.error("Could not mark read", errorMessage(e)),
  });
  return { ack, readAll };
}

export function AlertRow({ a, onAck, compact = false }: { a: AlertOut; onAck: (id: string) => void; compact?: boolean }) {
  return (
    <li className={cn("flex items-start gap-3 px-3 py-2", !a.read && "bg-accent-soft/30")}>
      <span className={cn("mt-1 size-1.5 shrink-0 rounded-full", a.read ? "bg-transparent" : "bg-accent-bright")} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={cn("rounded border px-1 py-px font-mono text-[10px]", SEVERITY[a.severity] ?? SEVERITY.INFO)}>{a.severity}</span>
          <TypeChip value={a.alert_type} />
          <span className={cn("font-medium", a.read ? "text-fg-muted" : "text-fg")}>{a.title}</span>
          {!compact ? <Mono className="text-fg-subtle">{a.display_id}</Mono> : null}
        </div>
        <p className={cn("mt-0.5 text-xs text-fg-muted", compact && "line-clamp-2")}>{a.message}</p>
        <p className="mt-0.5 font-mono text-[10px] text-fg-subtle">{formatTs(a.detected_at)}{a.source_label ? ` · ${a.source_label}` : ""}{a.delivered ? " · delivered" : ""}</p>
      </div>
      {!a.read ? <Button variant="ghost" size="icon-xs" aria-label="Acknowledge alert" onClick={() => onAck(a.id)}><Check /></Button> : null}
    </li>
  );
}

export function AlertsList({ caseId }: { caseId: string | null }) {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);
  const alerts = useAlerts({ case_id: caseId, unread: unreadOnly, page, page_size: PAGE_SIZE });
  const { ack, readAll } = useAlertActions();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Alerts {alerts.data ? <Mono className="text-fg-subtle">{alerts.data.total}</Mono> : null}</CardTitle>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-fg-muted"><Checkbox checked={unreadOnly} onCheckedChange={(v) => { setUnreadOnly(v === true); setPage(1); }} /> Unread only</label>
          <Button variant="outline" size="xs" onClick={() => readAll.mutate(caseId)} loading={readAll.isPending}><CheckCheck /> Mark all read</Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <QueryState query={alerts} rows={3} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title={unreadOnly ? "No unread alerts" : "No alerts yet"} description="Alerts are raised when a monitor detects a change in a watched public source." className="m-4" />}>
          {(d) => (
            <>
              <ul className="divide-y divide-border">{d.items.map((a) => <AlertRow key={a.id} a={a} onAck={(id) => ack.mutate(id)} />)}</ul>
              <div className="px-3 pb-2"><Pagination page={page} pageSize={PAGE_SIZE} total={d.total} onPage={setPage} /></div>
            </>
          )}
        </QueryState>
      </CardContent>
    </Card>
  );
}
