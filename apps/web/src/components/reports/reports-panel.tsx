"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, FileText } from "lucide-react";
import { apiPost, errorMessage } from "@/lib/api";
import { qk, useReports } from "@/lib/queries";
import type { ReportFormat, ReportOut } from "@/lib/types";
import { formatBytes, formatTs } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { Mono } from "@/components/shared/mono";
import { TypeChip } from "@/components/shared/badges";
import { EmptyState, QueryState } from "@/components/shared/states";
import { ExportLinks } from "./export-links";
import { ReportPreviewDialog } from "./report-preview-dialog";
import { cn } from "@/lib/utils";

const FORMATS: ReportFormat[] = ["pdf", "html", "markdown", "docx"];
const CLASSIFICATIONS = ["RESEARCH", "INTERNAL", "CONFIDENTIAL"];
const STATUS_STYLE: Record<string, string> = {
  PENDING: "text-fg-muted",
  GENERATING: "text-accent-bright",
  READY: "text-success",
  FAILED: "text-danger",
};

function ReportStatus({ r }: { r: ReportOut }) {
  const busy = r.status === "PENDING" || r.status === "GENERATING";
  return (
    <span className={cn("inline-flex items-center gap-1.5 font-mono text-[11px]", STATUS_STYLE[r.status] ?? "text-fg-muted")}>
      {busy ? <span className="size-1.5 animate-pulse rounded-full bg-current" /> : null}
      {r.status}
    </span>
  );
}

export function ReportsPanel({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const reports = useReports(caseId);
  const [format, setFormat] = useState<ReportFormat>("pdf");
  const [title, setTitle] = useState("");
  const [classification, setClassification] = useState("RESEARCH");
  const [previewId, setPreviewId] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => apiPost<ReportOut>("/reports", { case_id: caseId, format, title: title.trim() || null, classification }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: qk.reports(caseId) }); setTitle(""); toast.success("Report queued", `${r.display_id} · ${r.format}`); },
    onError: (e) => toast.error("Could not queue report", errorMessage(e)),
  });

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        <Card>
          <CardHeader><CardTitle>Generated reports</CardTitle></CardHeader>
          <CardContent className="p-0">
            <QueryState query={reports} rows={3} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No reports generated yet" description="Reports cite evidence IDs and source URLs for every statement; rejected evidence is excluded." className="m-4" />}>
              {(items) => (
                <Table>
                  <TableHeader>
                    <TableRow><TableHead>ID</TableHead><TableHead>Title</TableHead><TableHead>Format</TableHead><TableHead>Status</TableHead><TableHead>Size</TableHead><TableHead>Generated</TableHead><TableHead /></TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell><Mono className="text-fg-muted">{r.display_id}</Mono></TableCell>
                        <TableCell>
                          <span className="text-fg">{r.title}</span>
                          <span className="ml-2 text-[10px] uppercase text-fg-subtle">{r.classification}</span>
                          {r.error ? <p className="text-xs text-danger">{r.error}</p> : null}
                        </TableCell>
                        <TableCell><TypeChip value={r.format} /></TableCell>
                        <TableCell><ReportStatus r={r} /></TableCell>
                        <TableCell><Mono className="text-fg-subtle">{r.size_bytes ? formatBytes(r.size_bytes) : "—"}</Mono></TableCell>
                        <TableCell>
                          <Mono className="text-fg-subtle">{r.generated_at ? formatTs(r.generated_at) : "—"}</Mono>
                          {r.generation_ms != null ? <span className="ml-1 font-mono text-[10px] text-fg-subtle">({r.generation_ms} ms)</span> : null}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="xs" onClick={() => setPreviewId(r.id)} disabled={r.status !== "READY"}><Eye /> {r.format === "markdown" || r.format === "html" ? "Preview" : "Details"}</Button>
                            {r.status === "READY" ? (
                              <Button asChild variant="outline" size="xs"><a href={`/api/v1/reports/${r.id}/download`} download><Download /> Download</a></Button>
                            ) : (
                              <Button variant="outline" size="xs" disabled><Download /> Download</Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </QueryState>
          </CardContent>
        </Card>
        <ExportLinks caseId={caseId} />
      </div>
      <Card className="self-start">
        <CardHeader><CardTitle className="flex items-center gap-1.5"><FileText className="size-3.5" /> Generate report</CardTitle></CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
            <div className="space-y-1"><Label htmlFor="rp-title">Title</Label><Input id="rp-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Defaults to the case name" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="rp-format">Format</Label>
                <Select value={format} onValueChange={(v) => setFormat(v as ReportFormat)}>
                  <SelectTrigger id="rp-format"><SelectValue /></SelectTrigger>
                  <SelectContent>{FORMATS.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="rp-class">Classification</Label>
                <Select value={classification} onValueChange={setClassification}>
                  <SelectTrigger id="rp-class"><SelectValue /></SelectTrigger>
                  <SelectContent>{CLASSIFICATIONS.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <Button type="submit" size="sm" loading={create.isPending}>Generate</Button>
            <p className="text-[11px] text-fg-subtle">Generation runs in the background; the list refreshes until the report is ready.</p>
          </form>
        </CardContent>
      </Card>
      <ReportPreviewDialog reportId={previewId} onClose={() => setPreviewId(null)} />
    </div>
  );
}
