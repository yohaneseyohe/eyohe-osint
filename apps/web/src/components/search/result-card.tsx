"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bookmark, Crosshair, EyeOff, ExternalLink as OpenIcon, Plus } from "lucide-react";
import { apiPost, errorMessage } from "@/lib/api";
import type { ResultActionOut, SearchResultOut } from "@/lib/types";
import { formatDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { TypeChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { cn, truncate } from "@/lib/utils";

const STATUS_STYLE: Record<string, string> = {
  SAVED: "text-success",
  IGNORED: "text-fg-subtle line-through",
  NEW: "text-fg-subtle",
};

export function ResultCard({ r, caseId, onChanged }: { r: SearchResultOut; caseId: string | null; onChanged: (updated: SearchResultOut) => void }) {
  const qc = useQueryClient();
  const [claimOpen, setClaimOpen] = useState(false);
  const [claim, setClaim] = useState("");
  const act = useMutation({
    mutationFn: (body: { action: "save" | "ignore" | "add_evidence" | "investigate"; claim?: string }) =>
      apiPost<ResultActionOut>(`/search/results/${r.id}`, body),
    onSuccess: (out, body) => {
      if (caseId) {
        qc.invalidateQueries({ queryKey: ["case", caseId] });
        qc.invalidateQueries({ queryKey: ["cases"] });
      }
      const status = body.action === "ignore" ? "IGNORED" : body.action === "investigate" ? r.status : "SAVED";
      onChanged({ ...r, status, source_id: out.source_id ?? r.source_id });
      if (out.note) toast.info("Result noted", out.note);
      else if (out.evidence_display_id) toast.success("Evidence created", out.evidence_display_id);
      else if (out.target_id) toast.success("Target added", "The next investigation on this case can include it.");
      else toast.success(body.action === "ignore" ? "Result ignored" : "Source saved to case");
      setClaimOpen(false);
      setClaim("");
    },
    onError: (e) => toast.error("Action failed", errorMessage(e)),
  });
  const actionable = !!r.id && !!caseId;

  return (
    <li className={cn("glass rounded-lg border border-border px-4 py-3 animate-slide-in", r.status === "IGNORED" && "opacity-60")}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5 w-6 shrink-0 font-mono text-[11px] text-fg-subtle">#{r.rank}</span>
        <div className="min-w-0 flex-1">
          <a href={r.url} target="_blank" rel="noopener noreferrer nofollow" className="text-sm font-medium text-fg hover:text-accent-bright">
            {r.title || r.url}
          </a>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-fg-subtle">
            <Mono className="text-fg-muted">{r.domain}</Mono>
            <Mono className="truncate">{truncate(r.url, 90)}</Mono>
            {r.published_at ? <span>· {formatDate(r.published_at)}</span> : null}
            <span>· {r.engine}</span>
            {typeof r.relevance === "number" ? <span>· rel {r.relevance.toFixed(2)}</span> : null}
            <span className={cn("font-mono uppercase", STATUS_STYLE[r.status] ?? "")}>{r.status}</span>
          </div>
          {r.snippet ? <p className="mt-1.5 text-xs leading-relaxed text-fg-muted">{r.snippet}</p> : null}
          {r.entities && r.entities.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1">
              {r.entities.map((e, i) => (
                <span key={`${e.type}-${e.value}-${i}`} className="inline-flex items-center gap-1 rounded border border-border bg-bg-elevated px-1.5 py-0.5 text-[10px]">
                  <TypeChip value={e.type} className="border-0 bg-transparent px-0" /> <Mono className="text-fg-muted">{e.value}</Mono>
                </span>
              ))}
            </div>
          ) : null}
          {claimOpen ? (
            <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); act.mutate({ action: "add_evidence", claim: claim.trim() || undefined }); }}>
              <Input value={claim} onChange={(e) => setClaim(e.target.value)} placeholder="Claim this page supports (optional)" className="h-8 text-xs" autoFocus />
              <Button type="submit" size="sm" loading={act.isPending}>Create evidence</Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setClaimOpen(false)}>Cancel</Button>
            </form>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-1">
          <Button asChild variant="ghost" size="xs"><a href={r.url} target="_blank" rel="noopener noreferrer nofollow"><OpenIcon /> Open</a></Button>
          {actionable ? (
            <>
              <Button variant="ghost" size="xs" onClick={() => act.mutate({ action: "save" })} disabled={act.isPending || r.status === "SAVED"}><Bookmark /> Save</Button>
              <Button variant="ghost" size="xs" onClick={() => setClaimOpen((v) => !v)} disabled={act.isPending}><Plus /> Add Evidence</Button>
              <Button variant="ghost" size="xs" onClick={() => act.mutate({ action: "ignore" })} disabled={act.isPending || r.status === "IGNORED"}><EyeOff /> Ignore</Button>
              <Button variant="ghost" size="xs" onClick={() => act.mutate({ action: "investigate" })} disabled={act.isPending}><Crosshair /> Investigate</Button>
            </>
          ) : null}
        </div>
      </div>
    </li>
  );
}
