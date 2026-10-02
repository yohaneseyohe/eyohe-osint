"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { apiPost } from "@/lib/api";
import { useSearchProviders } from "@/lib/queries";
import type { SearchBranch, SearchCategory, SearchResponse, SearchResultOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { HealthChip } from "@/components/shared/badges";
import { CasePicker, useSelectedCaseId } from "@/components/shared/case-picker";
import { Mono } from "@/components/shared/mono";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, ErrorState } from "@/components/shared/states";
import { BranchesPanel } from "./branches-panel";
import { QueryHistory } from "./query-history";
import { ResultCard } from "./result-card";

const CATEGORIES: SearchCategory[] = ["general", "news", "code", "social", "documents"];

function ProviderStatus() {
  const prov = useSearchProviders();
  const h = prov.data?.health;
  return (
    <Card className="self-start">
      <CardHeader><CardTitle>Providers</CardTitle>{h ? <HealthChip value={h.status} /> : null}</CardHeader>
      <CardContent className="space-y-2 text-xs">
        {prov.isError ? <ErrorState error={prov.error} onRetry={() => prov.refetch()} compact /> : null}
        {h ? <p className="text-fg-muted">{h.message || "—"}</p> : <p className="text-fg-subtle">Checking…</p>}
        {h?.problems?.map((p, i) => <p key={i} className="text-warning">{p}</p>)}
        <ul className="divide-y divide-border rounded-md border border-border">
          {prov.data?.providers.map((p) => (
            <li key={p.name} className="flex items-center justify-between gap-2 px-2.5 py-1.5">
              <Mono className="text-fg">{p.name}</Mono>
              {p.configured ? <span className="text-success">configured</span> : <span className="truncate text-fg-subtle" title={p.note}>{p.note || "not configured"}</span>}
            </li>
          ))}
        </ul>
        <p className="text-fg-subtle">API keys live in <Mono>.env</Mono> and are never shown here.</p>
      </CardContent>
    </Card>
  );
}

export function QueryPlayground() {
  const params = useSearchParams();
  const urlQuery = params.get("q") ?? "";
  const caseId = useSelectedCaseId();
  const [q, setQ] = useState(urlQuery);
  const [category, setCategory] = useState<SearchCategory>("general");
  const [storeOnCase, setStoreOnCase] = useState(true);
  const [results, setResults] = useState<SearchResultOut[]>([]);
  const [seenUrlQuery, setSeenUrlQuery] = useState(urlQuery);
  if (urlQuery !== seenUrlQuery) {
    setSeenUrlQuery(urlQuery);
    setQ(urlQuery);
  }

  const search = useMutation({
    mutationFn: (body: { query: string; category: SearchCategory }) =>
      apiPost<SearchResponse>("/search", { ...body, max_results: 20, case_id: storeOnCase && caseId ? caseId : null }),
    onSuccess: (d) => setResults(d.results),
  });
  const run = (query: string, cat: SearchCategory = category) => {
    if (!query.trim()) return;
    setQ(query);
    setCategory(cat);
    search.mutate({ query: query.trim(), category: cat });
  };
  const pickBranch = (b: SearchBranch) => run(b.query, (CATEGORIES.includes(b.category as SearchCategory) ? b.category : "general") as SearchCategory);
  const effectiveCase = storeOnCase ? caseId : null;

  return (
    <div className="space-y-4">
      <PageHeader title="Query Playground" subtitle="Run one query across the configured providers, inspect raw hits, and promote them to sources or evidence." actions={<CasePicker />} />
      <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); run(q); }}>
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder='e.g. "example.com" site:github.com' className="w-full max-w-xl font-mono text-sm" aria-label="Search query" />
        <Select value={category} onValueChange={(v) => setCategory(v as SearchCategory)}>
          <SelectTrigger className="w-36" aria-label="Category"><SelectValue /></SelectTrigger>
          <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
        </Select>
        <Button type="submit" loading={search.isPending} disabled={!q.trim()}><Search /> Run query</Button>
        <label className="flex items-center gap-2 text-xs text-fg-muted">
          <Checkbox checked={storeOnCase} onCheckedChange={(v) => setStoreOnCase(v === true)} disabled={!caseId} /> Store on selected case
        </label>
      </form>
      <Tabs defaultValue="results">
        <TabsList>
          <TabsTrigger value="results">Results {results.length > 0 ? <Mono className="text-fg-subtle">{results.length}</Mono> : null}</TabsTrigger>
          <TabsTrigger value="history" disabled={!caseId}>Case history</TabsTrigger>
        </TabsList>
        <TabsContent value="results">
          <div className="grid gap-4 xl:grid-cols-3">
            <div className="space-y-3 xl:col-span-2">
              {search.isError ? <ErrorState error={search.error} /> : null}
              {search.data ? (
                <p className="font-mono text-[11px] text-fg-subtle">
                  provider {search.data.provider} · {search.data.elapsed_ms ?? "—"} ms{search.data.cache_hit ? " · cache hit" : ""}
                  {search.data.query_id ? <> · stored as query {search.data.query_id.slice(0, 8)}</> : " · not stored (no case)"}
                </p>
              ) : null}
              {search.data?.warnings.map((w, i) => <p key={i} className="rounded-md border border-warning/30 bg-warning/5 px-3 py-1.5 text-xs text-warning">{w}</p>)}
              {!search.data && !search.isError ? <EmptyState title="Enter a query or pick a branch to begin" className="py-10" /> : null}
              {search.data && results.length === 0 ? <EmptyState title="No results returned" description="The providers returned nothing for this query." className="py-10" /> : null}
              <ul className="space-y-2">
                {results.map((r, i) => (
                  <ResultCard key={r.id ?? `${r.url}-${i}`} r={r} caseId={effectiveCase} onChanged={(u) => setResults((prev) => prev.map((x) => (x === r ? u : x)))} />
                ))}
              </ul>
            </div>
            <div className="space-y-4">
              <BranchesPanel onPick={pickBranch} />
              <ProviderStatus />
            </div>
          </div>
        </TabsContent>
        <TabsContent value="history">{caseId ? <QueryHistory caseId={caseId} /> : null}</TabsContent>
      </Tabs>
    </div>
  );
}
