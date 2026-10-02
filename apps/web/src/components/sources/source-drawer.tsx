"use client";

import { useState } from "react";
import { GitCompare } from "lucide-react";
import { useSource, useSourceCompare } from "@/lib/queries";
import { formatTs } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent } from "@/components/ui/dialog";
import { DemoBadge, TierBadge, TypeChip } from "@/components/shared/badges";
import { ExternalLink } from "@/components/shared/external-link";
import { Mono } from "@/components/shared/mono";
import { KeyValue, SectionTitle } from "@/components/shared/page-header";
import { ErrorState, LoadingState } from "@/components/shared/states";
import { cn } from "@/lib/utils";

function DiffView({ sourceId }: { sourceId: string }) {
  const cmp = useSourceCompare(sourceId, true);
  if (cmp.isPending) return <LoadingState rows={4} />;
  if (cmp.isError) return <ErrorState error={cmp.error} onRetry={() => cmp.refetch()} compact />;
  const d = cmp.data;
  if (!d.from) return <p className="text-xs text-fg-subtle">{d.message ?? "Nothing to compare."}</p>;
  return (
    <div className="space-y-2">
      <p className="text-xs text-fg-muted">
        <Mono>{formatTs(d.from)}</Mono> → <Mono>{formatTs(d.to)}</Mono> ·{" "}
        {d.changed ? <span className="text-warning">content changed</span> : <span className="text-success">content identical</span>}
        {d.title_changed ? <> · title “{d.old_title}” → “{d.new_title}”</> : null}
      </p>
      {d.diff && d.diff.length > 0 ? (
        <pre className="max-h-96 overflow-auto rounded-md border border-border bg-bg-elevated p-3 font-mono text-[11px] leading-relaxed">
          {d.diff.map((line, i) => (
            <div
              key={i}
              className={cn(
                line.startsWith("+") && !line.startsWith("+++") && "bg-success/10 text-success",
                line.startsWith("-") && !line.startsWith("---") && "bg-danger/10 text-danger",
                line.startsWith("@@") && "text-accent-bright",
                !/^[+\-@]/.test(line) && "text-fg-muted",
              )}
            >
              {line || " "}
            </div>
          ))}
        </pre>
      ) : (
        <p className="text-xs text-fg-subtle">No textual differences.</p>
      )}
    </div>
  );
}

export function SourceDrawer({ sourceId, onClose }: { sourceId: string | null; onClose: () => void }) {
  const query = useSource(sourceId);
  const [compare, setCompare] = useState(false);
  const s = query.data;
  return (
    <Dialog open={!!sourceId} onOpenChange={(o) => { if (!o) { onClose(); setCompare(false); } }}>
      <DialogContent side="right" title={<span className="flex items-center gap-2">Source <Mono className="text-fg-subtle">{s?.display_id ?? ""}</Mono><DemoBadge show={s?.is_demo} /></span>} description={s?.title || s?.domain}>
        {query.isPending ? <div className="p-5"><LoadingState /></div> : null}
        {query.isError ? <div className="p-5"><ErrorState error={query.error} onRetry={() => query.refetch()} /></div> : null}
        {s ? (
          <DialogBody className="space-y-6">
            <div className="flex flex-wrap items-center gap-2">
              <TierBadge tier={s.tier} verbose />
              <TypeChip value={s.source_type} />
              <span className="text-xs text-fg-subtle">status {s.status}</span>
            </div>
            <ExternalLink href={s.url} max={120} />
            {s.canonical_url && s.canonical_url !== s.url ? <p className="text-xs text-fg-subtle">canonical: <Mono>{s.canonical_url}</Mono></p> : null}
            <dl className="grid grid-cols-2 gap-3 md:grid-cols-3">
              <KeyValue label="Domain" mono>{s.domain}</KeyValue>
              <KeyValue label="Publisher">{s.publisher || "—"}</KeyValue>
              <KeyValue label="Author">{s.author || "—"}</KeyValue>
              <KeyValue label="Published" mono>{s.published_at ? formatTs(s.published_at) : "—"}</KeyValue>
              <KeyValue label="Collected" mono>{formatTs(s.collected_at)}</KeyValue>
              <KeyValue label="Collector" mono>{s.collector || "—"}</KeyValue>
              <KeyValue label="Evidence items" mono>{s.evidence_count}</KeyValue>
            </dl>
            {s.reliability_note ? <p className="rounded-md border border-border bg-bg-elevated px-3 py-2 text-xs text-fg-muted">{s.reliability_note}</p> : null}

            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <SectionTitle>Snapshots ({s.snapshots.length})</SectionTitle>
                <Button variant="outline" size="xs" onClick={() => setCompare((v) => !v)} disabled={s.snapshots.length < 2}>
                  <GitCompare /> {compare ? "Hide comparison" : "Compare snapshots"}
                </Button>
              </div>
              {s.snapshots.length === 0 ? (
                <p className="text-xs text-fg-subtle">No snapshots stored.</p>
              ) : (
                <ul className="divide-y divide-border rounded-md border border-border">
                  {s.snapshots.map((sn) => (
                    <li key={sn.id} className="grid grid-cols-[auto_1fr_auto] items-center gap-3 px-3 py-2 text-xs">
                      <Mono className="text-fg-subtle">{formatTs(sn.retrieved_at)}</Mono>
                      <div className="min-w-0">
                        <p className="truncate text-fg">{sn.title || "(untitled)"}</p>
                        <p className="truncate font-mono text-[10px] text-fg-subtle">
                          HTTP {sn.http_status ?? "—"} · {sn.content_type || "?"} · {sn.text_chars} chars · {sn.fetch_ms ?? "—"} ms{sn.truncated ? " · truncated" : ""}
                        </p>
                      </div>
                      <Mono className="text-fg-subtle" title={sn.content_hash}>{sn.content_hash.slice(0, 10)}</Mono>
                    </li>
                  ))}
                </ul>
              )}
              {compare && sourceId ? <DiffView sourceId={sourceId} /> : null}
            </section>
          </DialogBody>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
