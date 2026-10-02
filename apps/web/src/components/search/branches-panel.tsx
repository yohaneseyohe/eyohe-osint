"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { GitBranch, Play } from "lucide-react";
import { apiPost, errorMessage } from "@/lib/api";
import type { SearchBranch } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Mono } from "@/components/shared/mono";
import { TypeChip } from "@/components/shared/badges";

/** Generates search branches for a target value; the analyst picks one to run. */
export function BranchesPanel({ onPick }: { onPick: (b: SearchBranch) => void }) {
  const [value, setValue] = useState("");
  const [objective, setObjective] = useState("");
  const gen = useMutation({
    mutationFn: () => apiPost<SearchBranch[]>("/search/branches", { value: value.trim(), objective: objective.trim() }),
    onError: (e) => void e,
  });
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-1.5"><GitBranch className="size-3.5" /> Search branches</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (value.trim()) gen.mutate(); }}>
          <Input value={value} onChange={(e) => setValue(e.target.value)} placeholder="Target value (domain, @handle, name…)" className="font-mono text-xs" aria-label="Branch target" />
          <Input value={objective} onChange={(e) => setObjective(e.target.value)} placeholder="Objective (optional)" className="text-xs" aria-label="Branch objective" />
          <Button type="submit" size="sm" variant="secondary" loading={gen.isPending} disabled={!value.trim()}>Generate branches</Button>
        </form>
        {gen.isError ? <p className="text-xs text-danger">{errorMessage(gen.error)}</p> : null}
        {gen.data ? (
          gen.data.length === 0 ? <p className="text-xs text-fg-subtle">No branches generated for this value.</p> : (
            <ul className="space-y-1">
              {gen.data.map((b, i) => (
                <li key={`${b.name}-${i}`}>
                  <button onClick={() => onPick(b)} className="flex w-full items-center gap-2 rounded-md border border-border bg-bg-elevated px-2.5 py-1.5 text-left text-xs hover:border-border-strong">
                    <Play className="size-3 shrink-0 text-accent-bright" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-fg">{b.name}</span>
                      <Mono className="block truncate text-fg-muted">{b.query}</Mono>
                    </span>
                    <TypeChip value={b.category} />
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : null}
      </CardContent>
    </Card>
  );
}
