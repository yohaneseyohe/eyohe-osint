"use client";

import { useState } from "react";
import { useCaseQueries, useCaseResults } from "@/lib/queries";
import { formatTs } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Mono } from "@/components/shared/mono";
import { TypeChip } from "@/components/shared/badges";
import { EmptyState, QueryState } from "@/components/shared/states";
import { ResultCard } from "./result-card";
import { cn } from "@/lib/utils";

export function QueryHistory({ caseId }: { caseId: string }) {
  const [queryId, setQueryId] = useState<string | null>(null);
  const queries = useCaseQueries(caseId);
  const results = useCaseResults(queryId ? caseId : null, { query_id: queryId, limit: 200 });
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Card>
        <CardHeader><CardTitle>Query history</CardTitle></CardHeader>
        <CardContent className="p-2">
          <QueryState query={queries} rows={4} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No stored queries for this case" className="py-6" />}>
            {(items) => (
              <ul className="max-h-[480px] space-y-0.5 overflow-y-auto">
                {items.map((q) => (
                  <li key={q.id}>
                    <button onClick={() => setQueryId(q.id)} className={cn("flex w-full flex-col gap-0.5 rounded-md px-2 py-1.5 text-left hover:bg-panel-2", queryId === q.id && "bg-accent-soft")}>
                      <span className="flex items-center gap-2 text-xs">
                        <TypeChip value={q.branch} />
                        <Mono className="truncate text-fg">{q.query}</Mono>
                      </span>
                      <span className="font-mono text-[10px] text-fg-subtle">
                        {q.provider} · {q.result_count} results · {q.status}{q.cache_hit ? " · cached" : ""} · {formatTs(q.executed_at ?? q.created_at)}
                      </span>
                      {q.error ? <span className="text-[10px] text-danger">{q.error}</span> : null}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </QueryState>
        </CardContent>
      </Card>
      <div className="xl:col-span-2">
        {!queryId ? <EmptyState title="Pick a query to see its stored results" className="py-10" /> : (
          <QueryState query={results} isEmpty={(d) => d.length === 0} empty={<EmptyState title="This query stored no results" className="py-10" />}>
            {(items) => <ul className="space-y-2">{items.map((r) => <ResultCard key={r.id ?? r.url} r={r} caseId={caseId} onChanged={() => results.refetch()} />)}</ul>}
          </QueryState>
        )}
      </div>
    </div>
  );
}
