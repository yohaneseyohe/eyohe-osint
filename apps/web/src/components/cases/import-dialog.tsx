"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { apiUpload, errorMessage } from "@/lib/api";
import { qk } from "@/lib/queries";
import type { ImportResult } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import { Mono } from "@/components/shared/mono";

const KINDS = [
  { value: "auto", label: "Detect from file" },
  { value: "json", label: "Eyohe JSON export package" },
  { value: "csv", label: "CSV of entities" },
  { value: "ioc", label: "Plain IOC list (one per line)" },
];

export function ImportDialog({ caseId, open, onOpenChange }: { caseId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState("auto");
  const [result, setResult] = useState<ImportResult | null>(null);
  const imp = useMutation({
    mutationFn: () => apiUpload<ImportResult>(`/cases/${caseId}/import?kind=${kind}`, file as File),
    onSuccess: (r) => {
      setResult(r);
      qc.invalidateQueries({ queryKey: qk.case(caseId) });
      qc.invalidateQueries({ queryKey: ["case", caseId] });
      qc.invalidateQueries({ queryKey: ["cases"] });
      toast.success("Import finished", `${r.entities} entities · ${r.sources} sources · ${r.evidence} evidence · ${r.skipped} skipped`);
    },
    onError: (e) => toast.error("Import failed", errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) { setFile(null); setResult(null); } }}>
      <DialogContent title="Import into case" description="Everything imported is attributed to the file (collector import:<filename>) and never marked as verified.">
        <DialogBody>
          <div className="space-y-1">
            <Label htmlFor="imp-file">File (max 20 MB)</Label>
            <input id="imp-file" type="file" accept=".json,.csv,.txt,application/json,text/csv,text/plain" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block w-full text-xs text-fg-muted file:mr-3 file:rounded-md file:border file:border-border file:bg-panel-2 file:px-3 file:py-1.5 file:text-xs file:text-fg" />
          </div>
          <div className="space-y-1">
            <Label htmlFor="imp-kind">Kind</Label>
            <Select value={kind} onValueChange={setKind}>
              <SelectTrigger id="imp-kind"><SelectValue /></SelectTrigger>
              <SelectContent>{KINDS.map((k) => <SelectItem key={k.value} value={k.value}>{k.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          {result ? (
            <div className="rounded-md border border-border bg-bg-elevated p-3 font-mono text-xs text-fg-muted">
              kind {result.kind} · entities <span className="text-fg">{result.entities}</span> · sources <span className="text-fg">{result.sources}</span> · evidence <span className="text-fg">{result.evidence}</span> · skipped <span className="text-fg">{result.skipped}</span>
            </div>
          ) : null}
          {file ? <p className="text-xs text-fg-subtle">Selected: <Mono>{file.name}</Mono> ({Math.round(file.size / 1024)} KB)</p> : null}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Close</Button>
          <Button onClick={() => imp.mutate()} loading={imp.isPending} disabled={!file}><Upload /> Import</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
