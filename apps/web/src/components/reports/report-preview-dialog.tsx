"use client";

import { useEffect, useState } from "react";
import { useReport } from "@/lib/queries";
import { Dialog, DialogBody, DialogContent } from "@/components/ui/dialog";
import { Mono } from "@/components/shared/mono";
import { SectionTitle } from "@/components/shared/page-header";
import { ErrorState, LoadingState } from "@/components/shared/states";
import { TypeChip } from "@/components/shared/badges";

function usePreviewText(reportId: string | null, enabled: boolean) {
  const [state, setState] = useState<{ text: string | null; error: string | null; loading: boolean }>({ text: null, error: null, loading: false });
  useEffect(() => {
    if (!reportId || !enabled) return;
    let cancelled = false;
    setState({ text: null, error: null, loading: true });
    fetch(`/api/v1/reports/${reportId}/preview`, { credentials: "same-origin" })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({ message: res.statusText }));
          throw new Error(typeof body.message === "string" ? body.message : "Preview unavailable");
        }
        return res.text();
      })
      .then((text) => { if (!cancelled) setState({ text, error: null, loading: false }); })
      .catch((e: Error) => { if (!cancelled) setState({ text: null, error: e.message, loading: false }); });
    return () => { cancelled = true; };
  }, [reportId, enabled]);
  return state;
}

export function ReportPreviewDialog({ reportId, onClose }: { reportId: string | null; onClose: () => void }) {
  const report = useReport(reportId);
  const r = report.data;
  const previewable = !!r && r.status === "READY" && (r.format === "markdown" || r.format === "html");
  const preview = usePreviewText(reportId, previewable);
  return (
    <Dialog open={!!reportId} onOpenChange={(o) => !o && onClose()}>
      <DialogContent side="right" className="max-w-4xl" title={<span className="flex items-center gap-2">Report <Mono className="text-fg-subtle">{r?.display_id ?? ""}</Mono>{r ? <TypeChip value={r.format} /> : null}</span>} description={r?.title}>
        {report.isPending ? <div className="p-5"><LoadingState /></div> : null}
        {report.isError ? <div className="p-5"><ErrorState error={report.error} onRetry={() => report.refetch()} /></div> : null}
        {r ? (
          <DialogBody className="space-y-5">
            <dl className="grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
              <div><dt className="text-fg-subtle uppercase text-[10px]">Status</dt><dd className="font-mono">{r.status}</dd></div>
              <div><dt className="text-fg-subtle uppercase text-[10px]">Classification</dt><dd>{r.classification}</dd></div>
              <div><dt className="text-fg-subtle uppercase text-[10px]">SHA-256</dt><dd><Mono title={r.sha256 ?? ""}>{r.sha256 ? r.sha256.slice(0, 16) + "…" : "—"}</Mono></dd></div>
              <div><dt className="text-fg-subtle uppercase text-[10px]">Generation</dt><dd className="font-mono">{r.generation_ms ?? "—"} ms</dd></div>
            </dl>
            {Object.keys(r.stats).length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(r.stats).map(([k, v]) => <span key={k} className="rounded border border-border bg-bg-elevated px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">{k}: <span className="text-fg">{String(v)}</span></span>)}
              </div>
            ) : null}
            <section className="space-y-2">
              <SectionTitle>Sections ({r.sections.length})</SectionTitle>
              {r.sections.length === 0 ? <p className="text-xs text-fg-subtle">No sections recorded.</p> : (
                <ul className="divide-y divide-border rounded-md border border-border">
                  {r.sections.map((s) => (
                    <li key={s.key} className="flex items-start gap-3 px-3 py-2 text-xs">
                      <Mono className="w-28 shrink-0 text-fg-subtle">{s.key}</Mono>
                      <span className="flex-1 text-fg">{s.title}</span>
                      <span className="font-mono text-fg-subtle">{s.cited_ids.length} cited</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            {previewable ? (
              <section className="space-y-2">
                <SectionTitle>Preview</SectionTitle>
                {preview.loading ? <LoadingState rows={6} /> : null}
                {preview.error ? <p className="text-xs text-danger">{preview.error}</p> : null}
                {preview.text !== null ? (
                  r.format === "html" ? (
                    <iframe title="Report preview" sandbox="" srcDoc={preview.text} className="h-[70vh] w-full rounded-md border border-border bg-white" />
                  ) : (
                    <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap rounded-md border border-border bg-bg-elevated p-3 font-mono text-[11px] leading-relaxed text-fg-muted">{preview.text}</pre>
                  )
                ) : null}
              </section>
            ) : r.status === "READY" ? <p className="text-xs text-fg-subtle">Inline preview is available for Markdown and HTML reports; download this {r.format} file instead.</p> : null}
          </DialogBody>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
