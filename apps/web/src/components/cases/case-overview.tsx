"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Archive, Copy, Crosshair, Play, Plus, Trash2 } from "lucide-react";
import { apiDelete, apiPatch, apiPost, errorMessage } from "@/lib/api";
import { qk, useInvestigations } from "@/lib/queries";
import type { CaseDetail, TargetOut } from "@/lib/types";
import { formatRelative, formatTs } from "@/lib/format";
import { PRIORITY_STYLE } from "@/lib/labels";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { InvestigationStatusChip, TypeChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { KeyValue } from "@/components/shared/page-header";
import { EmptyState, QueryState } from "@/components/shared/states";
import { NewInvestigationDialog } from "@/components/layout/new-investigation-dialog";
import { cn } from "@/lib/utils";

function Targets({ c }: { c: CaseDetail }) {
  const qc = useQueryClient();
  const [value, setValue] = useState("");
  const add = useMutation({
    mutationFn: () => apiPost<TargetOut>(`/cases/${c.id}/targets`, { value: value.trim() }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: qk.case(c.id) }); setValue(""); toast.success("Target added"); },
    onError: (e) => toast.error("Could not add target", errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiDelete(`/cases/${c.id}/targets/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: qk.case(c.id) }); toast.success("Target removed"); },
    onError: (e) => toast.error("Could not remove target", errorMessage(e)),
  });
  return (
    <Card>
      <CardHeader><CardTitle>Targets ({c.targets.length})</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {c.targets.length === 0 ? <p className="text-xs text-fg-subtle">No targets yet. Add one to plan an investigation.</p> : (
          <ul className="space-y-1.5">
            {c.targets.map((t) => (
              <li key={t.id} className="flex items-center gap-2 rounded-md border border-border bg-bg-elevated px-2.5 py-1.5">
                {t.is_primary ? <Crosshair className="size-3.5 text-accent-bright" aria-label="Primary" /> : null}
                <TypeChip value={t.type} />
                <Mono className="truncate text-sm text-fg">{t.value}</Mono>
                {t.label ? <span className="truncate text-xs text-fg-muted">{t.label}</span> : null}
                <Button variant="ghost" size="icon-xs" className="ml-auto" aria-label={`Remove target ${t.value}`} onClick={() => remove.mutate(t.id)} disabled={remove.isPending}><Trash2 /></Button>
              </li>
            ))}
          </ul>
        )}
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (value.trim()) add.mutate(); }}>
          <Input value={value} onChange={(e) => setValue(e.target.value)} placeholder="Add target (domain, IP, email, @handle…)" className="font-mono text-xs" aria-label="New target" />
          <Button type="submit" size="sm" variant="secondary" loading={add.isPending} disabled={!value.trim()}><Plus /> Add</Button>
        </form>
      </CardContent>
    </Card>
  );
}

function Investigations({ caseId, onNew }: { caseId: string; onNew: () => void }) {
  const query = useInvestigations({ case_id: caseId });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Investigations</CardTitle>
        <Button size="xs" onClick={onNew}><Play /> Start investigation</Button>
      </CardHeader>
      <CardContent className="p-2">
        <QueryState query={query} rows={3} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No investigations yet — start one" className="py-6" />}>
          {(items) => (
            <ul className="divide-y divide-border">
              {items.map((i) => (
                <li key={i.id}>
                  <Link href={`/investigations/${i.id}`} className="flex items-center gap-3 rounded-md px-2 py-2 hover:bg-panel-2/60">
                    <Mono className="text-fg-subtle">{i.display_id}</Mono>
                    <span className="min-w-0 flex-1 truncate text-sm text-fg">{i.name || i.request_text || i.objective}</span>
                    <InvestigationStatusChip value={i.status} />
                    <span className="hidden text-[11px] text-fg-subtle md:inline">{formatRelative(i.updated_at)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </QueryState>
      </CardContent>
    </Card>
  );
}

export function CaseOverview({ c }: { c: CaseDetail }) {
  const qc = useQueryClient();
  const [newOpen, setNewOpen] = useState(false);
  const clone = useMutation({
    mutationFn: () => apiPost<CaseDetail>(`/cases/${c.id}/clone`, { name: `${c.name} (copy)` }),
    onSuccess: (n) => { qc.invalidateQueries({ queryKey: ["cases"] }); toast.success("Case cloned", `${n.display_id} · ${n.name}`); window.location.assign(`/cases/${n.id}`); },
    onError: (e) => toast.error("Clone failed", errorMessage(e)),
  });
  const archive = useMutation({
    mutationFn: () => apiPatch<CaseDetail>(`/cases/${c.id}`, { status: c.status === "ARCHIVED" ? "ACTIVE" : "ARCHIVED" }),
    onSuccess: (n) => { qc.setQueryData(qk.case(c.id), { ...n, targets: c.targets }); qc.invalidateQueries({ queryKey: ["cases"] }); toast.success(n.status === "ARCHIVED" ? "Case archived" : "Case restored"); },
    onError: (e) => toast.error("Update failed", errorMessage(e)),
  });

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        <Card>
          <CardHeader>
            <CardTitle>Case</CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="xs" onClick={() => clone.mutate()} loading={clone.isPending}><Copy /> Clone</Button>
              <Button variant="outline" size="xs" onClick={() => archive.mutate()} loading={archive.isPending}><Archive /> {c.status === "ARCHIVED" ? "Restore" : "Archive"}</Button>
            </div>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <KeyValue label="Priority"><span className={cn("font-medium", PRIORITY_STYLE[c.priority])}>{c.priority}</span></KeyValue>
              <KeyValue label="Classification">{c.classification}</KeyValue>
              <KeyValue label="Created" mono>{formatTs(c.created_at)}</KeyValue>
              <KeyValue label="Updated" mono>{formatTs(c.updated_at)}</KeyValue>
              <div className="col-span-2 md:col-span-4">
                <KeyValue label="Objective">{c.objective || <span className="text-fg-subtle">No objective set.</span>}</KeyValue>
              </div>
              {c.description ? <div className="col-span-2 md:col-span-4"><KeyValue label="Description">{c.description}</KeyValue></div> : null}
              {c.tags.length > 0 ? (
                <div className="col-span-2 md:col-span-4">
                  <KeyValue label="Tags"><span className="flex flex-wrap gap-1">{c.tags.map((t, i) => <TypeChip key={i} value={String(t)} />)}</span></KeyValue>
                </div>
              ) : null}
            </dl>
          </CardContent>
        </Card>
        <Investigations caseId={c.id} onNew={() => setNewOpen(true)} />
      </div>
      <div className="space-y-4">
        <Card>
          <CardHeader><CardTitle>Counters</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            {[["Evidence", c.evidence_count], ["Sources", c.source_count], ["Entities", c.entity_count], ["Findings", c.finding_count]].map(([l, n]) => (
              <div key={String(l)} className="rounded-md border border-border bg-bg-elevated px-3 py-2">
                <div className="text-[10px] uppercase tracking-wider text-fg-subtle">{l}</div>
                <div className="font-mono text-xl text-fg">{n}</div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Targets c={c} />
      </div>
      <NewInvestigationDialog open={newOpen} onOpenChange={setNewOpen} defaultCaseId={c.id} />
    </div>
  );
}
