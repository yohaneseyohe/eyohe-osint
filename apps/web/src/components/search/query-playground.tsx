"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Search } from "lucide-react";
import { useHealth } from "@/lib/queries";
import { useSearch, SEARCH_AVAILABLE } from "@/hooks/use-search";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { HealthChip } from "@/components/shared/badges";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { Mono } from "@/components/shared/mono";

export function QueryPlayground() {
  const params = useSearchParams();
  const urlQuery = params.get("q") ?? "";
  const [q, setQ] = useState(urlQuery);
  const [submitted, setSubmitted] = useState<string | null>(urlQuery || null);
  // Adopt a new ?q= from the command palette while already on this page.
  const [seenUrlQuery, setSeenUrlQuery] = useState(urlQuery);
  if (urlQuery !== seenUrlQuery) {
    setSeenUrlQuery(urlQuery);
    setQ(urlQuery);
    setSubmitted(urlQuery || null);
  }
  const health = useHealth(30_000);
  const search = useSearch();
  const comp = health.data?.components.find((c) => c.name === "search");
  const configured = Array.isArray(comp?.detail.configured) ? (comp.detail.configured as string[]) : [];
  const problems = Array.isArray(comp?.detail.problems) ? (comp.detail.problems as string[]) : [];

  return (
    <div className="space-y-4">
      <PageHeader title="Query Playground" subtitle="Run a single query across the configured search providers and inspect raw results before they become sources." />
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) { setSubmitted(q.trim()); search.mutate(q.trim()); } }}>
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder='e.g. "example.com" site:github.com' className="max-w-2xl font-mono text-sm" aria-label="Search query" />
        <Button type="submit" disabled={!q.trim()}><Search /> Run query</Button>
      </form>
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader><CardTitle>Results</CardTitle></CardHeader>
          <CardContent>
            {!submitted ? <EmptyState title="Enter a query to begin" className="py-8" /> : !SEARCH_AVAILABLE ? (
              <EmptyState
                title="Search providers arrive in Phase 3"
                description={<>The query <Mono className="text-fg">{submitted}</Mono> was not sent anywhere. The API does not expose <Mono>POST /api/v1/search</Mono> yet; this page is wired to use it as soon as it exists.</>}
                className="py-8"
              />
            ) : (
              <Table>
                <TableHeader><TableRow><TableHead>Title</TableHead><TableHead>URL</TableHead><TableHead>Provider</TableHead></TableRow></TableHeader>
                <TableBody>{search.data?.results.map((r) => <TableRow key={r.url}><TableCell>{r.title}</TableCell><TableCell><Mono>{r.url}</Mono></TableCell><TableCell>{r.provider}</TableCell></TableRow>)}</TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
        <Card className="self-start">
          <CardHeader><CardTitle>Provider status</CardTitle>{comp ? <HealthChip value={comp.status} /> : null}</CardHeader>
          <CardContent className="space-y-2 text-xs">
            {comp ? (
              <>
                <p className="text-fg-muted">{comp.message || "No message."}</p>
                <p className="text-fg-subtle">Configured: {configured.length > 0 ? configured.join(", ") : "none"}</p>
                {problems.map((p, i) => <p key={i} className="text-warning">{p}</p>)}
              </>
            ) : <p className="text-fg-subtle">{health.isPending ? "Checking…" : "Search component not reported by /health."}</p>}
            <p className="text-fg-subtle">Provider API keys live in <Mono>.env</Mono> and are never shown here.</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
