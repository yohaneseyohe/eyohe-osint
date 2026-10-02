"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Play, Plus, Trash2 } from "lucide-react";
import { apiDelete, apiPatch, apiPost, errorMessage } from "@/lib/api";
import { useMonitors } from "@/lib/queries";
import type { MonitorOut } from "@/lib/types";
import { formatRelative, formatTs } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { Mono } from "@/components/shared/mono";
import { TypeChip } from "@/components/shared/badges";
import { EmptyState, QueryState } from "@/components/shared/states";
import { CreateMonitorDialog } from "./create-monitor-dialog";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<string, string> = { OK: "text-success", CHANGED: "text-warning", ERROR: "text-danger", FAILED: "text-danger" };

export function MonitorsTable({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const monitors = useMonitors(caseId);
  const [createOpen, setCreateOpen] = useState(false);
  const refresh = () => qc.invalidateQueries({ queryKey: ["monitors"] });
  const toggle = useMutation({
    mutationFn: (m: MonitorOut) => apiPatch<MonitorOut>(`/monitors/${m.id}`, { enabled: !m.enabled }),
    onSuccess: (m) => { refresh(); toast.success(m.enabled ? "Monitor enabled" : "Monitor paused"); },
    onError: (e) => toast.error("Update failed", errorMessage(e)),
  });
  const run = useMutation({
    mutationFn: (id: string) => apiPost<{ queued: boolean; job: string }>(`/monitors/${id}/run`),
    onSuccess: () => { toast.success("Check queued", "Results and alerts appear when the run finishes."); window.setTimeout(refresh, 4000); },
    onError: (e) => toast.error("Could not queue run", errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiDelete(`/monitors/${id}`),
    onSuccess: () => { refresh(); toast.success("Monitor deleted"); },
    onError: (e) => toast.error("Delete failed", errorMessage(e)),
  });

  return (
    <Card>
      <CardHeader><CardTitle>Monitors</CardTitle><Button size="xs" onClick={() => setCreateOpen(true)}><Plus /> New monitor</Button></CardHeader>
      <CardContent className="p-0">
        <QueryState query={monitors} rows={3} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No monitors on this case" description="Create one to re-check DNS, certificates, search results or social mentions on a schedule." className="m-4" action={<Button size="sm" onClick={() => setCreateOpen(true)}><Plus /> New monitor</Button>} />}>
          {(items) => (
            <Table>
              <TableHeader>
                <TableRow><TableHead>Monitor</TableHead><TableHead>Target</TableHead><TableHead>Checks</TableHead><TableHead>Schedule</TableHead><TableHead>Last run</TableHead><TableHead>Next run</TableHead><TableHead>Status</TableHead><TableHead>On</TableHead><TableHead /></TableRow>
              </TableHeader>
              <TableBody>
                {items.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell><span className="text-fg">{m.name}</span><br /><Mono className="text-fg-subtle">{m.display_id}</Mono></TableCell>
                    <TableCell><span className="flex items-center gap-1.5"><TypeChip value={m.target_type} /><Mono className="text-fg-muted">{m.target_value}</Mono></span></TableCell>
                    <TableCell><div className="flex flex-wrap gap-1">{m.checks.map((c) => <Mono key={c} className="rounded border border-border px-1 text-[10px] text-fg-muted">{c}</Mono>)}</div></TableCell>
                    <TableCell><Mono className="text-fg-muted">{m.schedule}</Mono></TableCell>
                    <TableCell className="text-xs text-fg-muted">{m.last_run_at ? <span title={formatTs(m.last_run_at)}>{formatRelative(m.last_run_at)}</span> : "never"}<br /><span className="font-mono text-[10px] text-fg-subtle">{m.run_count} runs{m.has_baseline ? " · baseline" : ""}</span></TableCell>
                    <TableCell><Mono className="text-fg-subtle">{m.next_run_at ? formatTs(m.next_run_at) : "—"}</Mono></TableCell>
                    <TableCell>
                      <span className={cn("font-mono text-[11px]", STATUS_STYLE[m.last_status ?? ""] ?? "text-fg-subtle")}>{m.last_status ?? "—"}</span>
                      {m.last_error ? <p className="max-w-[16rem] truncate text-[11px] text-danger" title={m.last_error}>{m.last_error}</p> : null}
                    </TableCell>
                    <TableCell><Switch checked={m.enabled} onCheckedChange={() => toggle.mutate(m)} disabled={toggle.isPending} aria-label={`${m.enabled ? "Pause" : "Enable"} ${m.name}`} /></TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon-xs" aria-label="Run now" onClick={() => run.mutate(m.id)} disabled={run.isPending}><Play /></Button>
                        <Button variant="ghost" size="icon-xs" aria-label="Delete monitor" onClick={() => remove.mutate(m.id)} disabled={remove.isPending}><Trash2 /></Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </QueryState>
      </CardContent>
      <CreateMonitorDialog caseId={caseId} open={createOpen} onOpenChange={setCreateOpen} />
    </Card>
  );
}
