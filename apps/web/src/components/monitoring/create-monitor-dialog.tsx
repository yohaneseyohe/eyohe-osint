"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiPost, errorMessage } from "@/lib/api";
import { useCase } from "@/lib/queries";
import type { MonitorCheck, MonitorCreate, MonitorOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogBody, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import { Mono } from "@/components/shared/mono";
import { TypeChip } from "@/components/shared/badges";

const CHECKS: MonitorCheck[] = ["dns", "ct", "search", "github", "reddit", "news"];
const SCHEDULES = ["hourly", "daily", "weekly"];
const CUSTOM = "__custom__";

export function CreateMonitorDialog({ caseId, open, onOpenChange }: { caseId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="New monitor" description="Re-checks public sources on a schedule and raises an alert when something changes.">
        <MonitorForm caseId={caseId} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function MonitorForm({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const qc = useQueryClient();
  const kase = useCase(caseId);
  const [name, setName] = useState("");
  const [targetId, setTargetId] = useState<string>(CUSTOM);
  const [targetValue, setTargetValue] = useState("");
  const [checks, setChecks] = useState<Set<string>>(new Set(["dns", "search"]));
  const [schedule, setSchedule] = useState("daily");
  const [keywords, setKeywords] = useState("");
  const [notify, setNotify] = useState({ telegram: false, webhook: false, email: false, email_to: "" });
  const create = useMutation({
    mutationFn: () => {
      const body: MonitorCreate = {
        case_id: caseId,
        name: name.trim(),
        target_id: targetId === CUSTOM ? null : targetId,
        target_value: targetId === CUSTOM ? targetValue.trim() : null,
        checks: [...checks],
        schedule,
        keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
        notify: { telegram: notify.telegram, webhook: notify.webhook, email: notify.email, ...(notify.email ? { email_to: notify.email_to.trim() } : {}) },
      };
      return apiPost<MonitorOut>("/monitors", body);
    },
    onSuccess: (m) => { qc.invalidateQueries({ queryKey: ["monitors"] }); toast.success("Monitor created", `${m.display_id} · next run ${m.next_run_at ?? "pending"}`); onDone(); },
    onError: (e) => toast.error("Could not create monitor", errorMessage(e)),
  });
  const valid = name.trim() && checks.size > 0 && (targetId !== CUSTOM || targetValue.trim());
  const toggle = (c: string) => setChecks((prev) => { const n = new Set(prev); if (n.has(c)) n.delete(c); else n.add(c); return n; });

  return (
    <form onSubmit={(e) => { e.preventDefault(); if (valid) create.mutate(); }}>
      <DialogBody>
        <div className="space-y-1"><Label htmlFor="mn-name">Name</Label><Input id="mn-name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus /></div>
        <div className="space-y-1">
          <Label htmlFor="mn-target">Target</Label>
          <Select value={targetId} onValueChange={setTargetId}>
            <SelectTrigger id="mn-target"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={CUSTOM}>Custom value…</SelectItem>
              {kase.data?.targets.map((t) => <SelectItem key={t.id} value={t.id}><span className="flex items-center gap-2"><TypeChip value={t.type} /><Mono>{t.value}</Mono></span></SelectItem>)}
            </SelectContent>
          </Select>
          {targetId === CUSTOM ? <Input value={targetValue} onChange={(e) => setTargetValue(e.target.value)} placeholder="example.com, @handle, name… (type is detected)" className="mt-1 font-mono text-xs" aria-label="Target value" /> : null}
        </div>
        <div className="space-y-1">
          <Label>Checks</Label>
          <div className="flex flex-wrap gap-3">
            {CHECKS.map((c) => (
              <label key={c} className="flex items-center gap-1.5 text-xs text-fg"><Checkbox checked={checks.has(c)} onCheckedChange={() => toggle(c)} /> <Mono>{c}</Mono></label>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label htmlFor="mn-schedule">Schedule</Label>
            <Select value={SCHEDULES.includes(schedule) ? schedule : "cron"} onValueChange={(v) => setSchedule(v === "cron" ? "0 */6 * * *" : v)}>
              <SelectTrigger id="mn-schedule"><SelectValue /></SelectTrigger>
              <SelectContent>{SCHEDULES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}<SelectItem value="cron">cron expression…</SelectItem></SelectContent>
            </Select>
            {!SCHEDULES.includes(schedule) ? <Input value={schedule} onChange={(e) => setSchedule(e.target.value)} className="mt-1 font-mono text-xs" aria-label="Cron expression" /> : null}
          </div>
          <div className="space-y-1"><Label htmlFor="mn-kw">Keywords</Label><Input id="mn-kw" value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="comma, separated" /></div>
        </div>
        <div className="space-y-1">
          <Label>Notify</Label>
          <div className="flex flex-wrap items-center gap-3 text-xs text-fg">
            <label className="flex items-center gap-1.5"><Checkbox checked={notify.telegram} onCheckedChange={(v) => setNotify({ ...notify, telegram: v === true })} /> Telegram</label>
            <label className="flex items-center gap-1.5"><Checkbox checked={notify.webhook} onCheckedChange={(v) => setNotify({ ...notify, webhook: v === true })} /> Webhook</label>
            <label className="flex items-center gap-1.5"><Checkbox checked={notify.email} onCheckedChange={(v) => setNotify({ ...notify, email: v === true })} /> Email</label>
            {notify.email ? <Input type="email" value={notify.email_to} onChange={(e) => setNotify({ ...notify, email_to: e.target.value })} placeholder="recipient@example.org" className="h-8 w-56 text-xs" aria-label="Email recipient" /> : null}
          </div>
          <p className="text-[11px] text-fg-subtle">Channels are delivered only if configured in <Mono>.env</Mono>; alerts always appear in the app.</p>
        </div>
      </DialogBody>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
        <Button type="submit" loading={create.isPending} disabled={!valid}>Create monitor</Button>
      </DialogFooter>
    </form>
  );
}
