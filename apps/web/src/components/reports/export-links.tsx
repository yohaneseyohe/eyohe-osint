import { Download } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Mono } from "@/components/shared/mono";

const CSV_KINDS = ["entities", "evidence", "sources", "relationships", "findings"] as const;

/** Same-origin download links; the API sets content-disposition so plain anchors work. */
export function ExportLinks({ caseId }: { caseId: string }) {
  const href = (format: string, kind?: string) => `/api/v1/cases/${caseId}/export?format=${format}${kind ? `&kind=${kind}` : ""}`;
  const link = (label: string, h: string) => (
    <a key={h} href={h} download className="inline-flex items-center gap-1.5 rounded-md border border-border bg-bg-elevated px-2.5 py-1.5 text-xs text-fg hover:border-border-strong">
      <Download className="size-3.5 text-fg-subtle" /> {label}
    </a>
  );
  return (
    <Card>
      <CardHeader><CardTitle>Exports</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div>
          <p className="mb-1.5 text-[10px] uppercase tracking-wider text-fg-subtle">Packages</p>
          <div className="flex flex-wrap gap-2">
            {link("JSON package (re-importable)", href("json"))}
            {link("GraphML", href("graphml"))}
            {link("Markdown report", href("markdown"))}
          </div>
        </div>
        <div>
          <p className="mb-1.5 text-[10px] uppercase tracking-wider text-fg-subtle">CSV</p>
          <div className="flex flex-wrap gap-2">{CSV_KINDS.map((k) => link(k, href("csv", k)))}</div>
        </div>
        <p className="text-[11px] text-fg-subtle">Every export is recorded in the audit log. Files are named after the case <Mono>display_id</Mono>.</p>
      </CardContent>
    </Card>
  );
}
