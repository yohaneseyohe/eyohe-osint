"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiPost, errorMessage } from "@/lib/api";
import type { CaseCreate, CaseDetail } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";

const PRIORITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const CLASSIFICATIONS = ["RESEARCH", "INTERNAL", "CONFIDENTIAL"];

export function CreateCaseDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const qc = useQueryClient();
  const [form, setForm] = useState({ name: "", description: "", objective: "", priority: "MEDIUM", classification: "RESEARCH", targets: "", tags: "" });
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  const create = useMutation({
    mutationFn: () => {
      const body: CaseCreate = {
        name: form.name.trim(),
        description: form.description.trim(),
        objective: form.objective.trim(),
        priority: form.priority,
        classification: form.classification,
        targets: form.targets.split(/[\n,]/).map((t) => t.trim()).filter(Boolean),
        tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
      };
      return apiPost<CaseDetail>("/cases", body);
    },
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["cases"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Case created", `${c.display_id} · ${c.name}`);
      onOpenChange(false);
      setForm({ name: "", description: "", objective: "", priority: "MEDIUM", classification: "RESEARCH", targets: "", tags: "" });
      router.push(`/cases/${c.id}`);
    },
    onError: (e) => toast.error("Could not create case", errorMessage(e)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="New case" description="A case groups targets, investigations and all evidence collected for them.">
        <form onSubmit={(e) => { e.preventDefault(); if (form.name.trim()) create.mutate(); }}>
          <DialogBody>
            <div className="space-y-1.5">
              <Label htmlFor="c-name">Name</Label>
              <Input id="c-name" value={form.name} onChange={(e) => set("name")(e.target.value)} required autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-objective">Objective</Label>
              <Textarea id="c-objective" value={form.objective} onChange={(e) => set("objective")(e.target.value)} rows={2} placeholder="What question should this case answer?" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-targets">Targets</Label>
              <Textarea id="c-targets" value={form.targets} onChange={(e) => set("targets")(e.target.value)} rows={2} className="font-mono text-xs" placeholder={"One per line or comma separated\nexample.com, @handle, 203.0.113.10"} />
              <p className="text-[11px] text-fg-subtle">Target types (domain, IP, email, username…) are detected automatically.</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="c-priority">Priority</Label>
                <Select value={form.priority} onValueChange={set("priority")}>
                  <SelectTrigger id="c-priority"><SelectValue /></SelectTrigger>
                  <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="c-class">Classification</Label>
                <Select value={form.classification} onValueChange={set("classification")}>
                  <SelectTrigger id="c-class"><SelectValue /></SelectTrigger>
                  <SelectContent>{CLASSIFICATIONS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-tags">Tags</Label>
              <Input id="c-tags" value={form.tags} onChange={(e) => set("tags")(e.target.value)} placeholder="comma, separated" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-desc">Description</Label>
              <Textarea id="c-desc" value={form.description} onChange={(e) => set("description")(e.target.value)} rows={2} />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" loading={create.isPending} disabled={!form.name.trim()}>Create case</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
