"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Pin, Trash2 } from "lucide-react";
import { apiDelete, apiPost, errorMessage } from "@/lib/api";
import { qk, useNotes } from "@/lib/queries";
import type { NoteOut } from "@/lib/types";
import { formatTs } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { Mono } from "@/components/shared/mono";
import { EmptyState, QueryState } from "@/components/shared/states";

export function CaseNotes({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const notes = useNotes(caseId);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [pinned, setPinned] = useState(false);
  const create = useMutation({
    mutationFn: () => apiPost<NoteOut>(`/cases/${caseId}/notes`, { title: title.trim(), body, pinned }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: qk.notes(caseId) }); setTitle(""); setBody(""); setPinned(false); toast.success("Note saved"); },
    onError: (e) => toast.error("Could not save note", errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiDelete(`/cases/${caseId}/notes/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: qk.notes(caseId) }); toast.success("Note deleted"); },
    onError: (e) => toast.error("Could not delete note", errorMessage(e)),
  });

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="space-y-3 xl:col-span-2">
        <QueryState query={notes} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No notes yet" description="Analyst notes support Markdown and stay with the case." />}>
          {(items) =>
            [...items].sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.updated_at.localeCompare(a.updated_at)).map((n) => (
              <Card key={n.id} className={n.pinned ? "border-accent/40" : undefined}>
                <CardHeader className="py-2">
                  <div className="flex items-center gap-2">
                    {n.pinned ? <Pin className="size-3.5 text-accent-bright" aria-label="Pinned" /> : null}
                    <CardTitle className="normal-case tracking-normal text-sm text-fg">{n.title || "Untitled note"}</CardTitle>
                    <Mono className="text-fg-subtle">{formatTs(n.updated_at)}</Mono>
                  </div>
                  <Button variant="ghost" size="icon-xs" aria-label="Delete note" onClick={() => remove.mutate(n.id)}><Trash2 /></Button>
                </CardHeader>
                <CardContent className="prose-eyohe text-sm text-fg-muted">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{n.body}</ReactMarkdown>
                </CardContent>
              </Card>
            ))
          }
        </QueryState>
      </div>
      <Card className="self-start">
        <CardHeader><CardTitle>New note</CardTitle></CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (body.trim()) create.mutate(); }}>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title (optional)" aria-label="Note title" />
            <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={8} placeholder="Markdown supported…" aria-label="Note body" className="font-mono text-xs" />
            <label className="flex items-center gap-2 text-xs text-fg-muted"><Checkbox checked={pinned} onCheckedChange={(v) => setPinned(v === true)} /> Pin to top</label>
            <Button type="submit" size="sm" loading={create.isPending} disabled={!body.trim()}>Save note</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
