"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, RefreshCw, Square } from "lucide-react";
import { apiPost, errorMessage } from "@/lib/api";
import { qk } from "@/lib/queries";
import type { InvestigationDetail } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";

export function InvestigationControls({ inv }: { inv: InvestigationDetail }) {
  const qc = useQueryClient();
  const refresh = (d: InvestigationDetail) => {
    qc.setQueryData(qk.investigation(inv.id), d);
    qc.invalidateQueries({ queryKey: qk.invStatus(inv.id) });
    qc.invalidateQueries({ queryKey: ["investigations"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const approve = useMutation({
    mutationFn: () => apiPost<InvestigationDetail>(`/investigations/${inv.id}/approve`),
    onSuccess: (d) => { refresh(d); toast.success("Plan approved", "Collection is running."); },
    onError: (e) => toast.error("Approve failed", errorMessage(e)),
  });
  const control = useMutation({
    mutationFn: (action: "pause" | "resume" | "stop") => apiPost<InvestigationDetail>(`/investigations/${inv.id}/control`, { action }),
    onSuccess: (d, action) => { refresh(d); toast.success(`Investigation ${action === "stop" ? "stopped" : action + "d"}`); },
    onError: (e) => toast.error("Control failed", errorMessage(e)),
  });
  const replan = useMutation({
    mutationFn: () => apiPost<InvestigationDetail>(`/investigations/${inv.id}/plan?use_ai=true`),
    onSuccess: (d) => { refresh(d); toast.success("Plan regenerated"); },
    onError: (e) => toast.error("Re-plan failed", errorMessage(e)),
  });

  const s = inv.status;
  const busy = approve.isPending || control.isPending || replan.isPending;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {s === "AWAITING_APPROVAL" || s === "DRAFT" ? (
        <Button onClick={() => approve.mutate()} loading={approve.isPending} disabled={busy || inv.tasks.filter((t) => t.enabled).length === 0}>
          <Play /> Approve &amp; Run
        </Button>
      ) : null}
      {s === "RUNNING" || s === "VERIFYING" ? (
        <Button variant="secondary" onClick={() => control.mutate("pause")} loading={control.isPending} disabled={busy}><Pause /> Pause</Button>
      ) : null}
      {s === "PAUSED" ? (
        <Button onClick={() => control.mutate("resume")} loading={control.isPending} disabled={busy}><Play /> Resume</Button>
      ) : null}
      {s === "RUNNING" || s === "VERIFYING" || s === "PAUSED" ? (
        <Button variant="destructive" onClick={() => control.mutate("stop")} loading={control.isPending} disabled={busy}><Square /> Stop</Button>
      ) : null}
      {s === "DRAFT" || s === "AWAITING_APPROVAL" || s === "FAILED" || s === "STOPPED" || s === "COMPLETED" ? (
        <Button variant="outline" onClick={() => replan.mutate()} loading={replan.isPending} disabled={busy}><RefreshCw /> Re-plan</Button>
      ) : null}
    </div>
  );
}
