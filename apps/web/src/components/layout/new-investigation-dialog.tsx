"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { apiPost, errorMessage } from "@/lib/api";
import { useCases } from "@/lib/queries";
import type { CaseCreate, CaseDetail, InvestigationDetail } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { Mono } from "@/components/shared/mono";

const NEW_CASE = "__new__";

interface Props {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  defaultCaseId?: string;
}

export function NewInvestigationDialog({ open, onOpenChange, defaultCaseId }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="New Investigation"
        description="Plan a public-source investigation. You review the plan before anything runs."
      >
        <NewInvestigationForm onOpenChange={onOpenChange} defaultCaseId={defaultCaseId} />
      </DialogContent>
    </Dialog>
  );
}

// Mounted only while the dialog is open, so every open starts from a clean form.
function NewInvestigationForm({ onOpenChange, defaultCaseId }: Omit<Props, "open">) {
  const router = useRouter();
  const qc = useQueryClient();
  const cases = useCases({ page_size: 200 });
  const [caseId, setCaseId] = useState<string>(defaultCaseId ?? NEW_CASE);
  const [caseName, setCaseName] = useState("");
  const [target, setTarget] = useState("");
  const [objective, setObjective] = useState("");
  const [useAi, setUseAi] = useState(true);

  const start = useMutation({
    mutationFn: async () => {
      let id = caseId;
      if (id === NEW_CASE) {
        const body: CaseCreate = {
          name: caseName.trim() || `Investigation of ${target.trim()}`,
          objective: objective.trim(),
          targets: target.trim() ? [target.trim()] : [],
        };
        const created = await apiPost<CaseDetail>("/cases", body);
        id = created.id;
      } else if (target.trim()) {
        // Existing case: register the target so the planner can resolve its type.
        await apiPost(`/cases/${id}/targets`, { value: target.trim() }).catch(() => undefined);
      }
      const request = [target.trim(), objective.trim()].filter(Boolean).join(" — ");
      return apiPost<InvestigationDetail>("/investigations/start", {
        case_id: id,
        request_text: request,
        use_ai: useAi,
        auto_approve: false,
      });
    },
    onSuccess: (inv) => {
      qc.invalidateQueries({ queryKey: ["cases"] });
      qc.invalidateQueries({ queryKey: ["investigations"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Investigation planned", `${inv.display_id} is awaiting your approval.`);
      onOpenChange(false);
      router.push(`/investigations/${inv.id}`);
    },
    onError: (e) => toast.error("Could not start investigation", errorMessage(e)),
  });

  const canSubmit = target.trim().length > 0 || objective.trim().length > 0;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) start.mutate();
      }}
    >
      <DialogBody>
        <div className="space-y-1.5">
          <Label htmlFor="ni-case">Case</Label>
          <Select value={caseId} onValueChange={setCaseId}>
            <SelectTrigger id="ni-case">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NEW_CASE}>
                <span className="flex items-center gap-2">
                  <Plus className="size-3.5" /> Create a new case
                </span>
              </SelectItem>
              {cases.data?.items.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  <span className="flex items-center gap-2">
                    <Mono className="text-fg-subtle">{c.display_id}</Mono> {c.name}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {caseId === NEW_CASE ? (
          <div className="space-y-1.5">
            <Label htmlFor="ni-name">Case name</Label>
            <Input
              id="ni-name"
              value={caseName}
              onChange={(e) => setCaseName(e.target.value)}
              placeholder="Defaults to the target"
            />
          </div>
        ) : null}
        <div className="space-y-1.5">
          <Label htmlFor="ni-target">Target</Label>
          <Input
            id="ni-target"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="example.com, 203.0.113.10, @handle, person or organisation"
            className="font-mono text-sm"
            autoFocus
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ni-objective">Objective</Label>
          <Textarea
            id="ni-objective"
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            placeholder="What should the investigation establish?"
            rows={3}
          />
        </div>
        <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
          <div>
            <p className="text-sm text-fg">Plan with the local AI model</p>
            <p className="text-xs text-fg-muted">
              Falls back to the deterministic template plan if Ollama is unavailable.
            </p>
          </div>
          <Switch checked={useAi} onCheckedChange={setUseAi} aria-label="Use AI planner" />
        </div>
      </DialogBody>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button type="submit" loading={start.isPending} disabled={!canSubmit}>
          Plan investigation
        </Button>
      </DialogFooter>
    </form>
  );
}
