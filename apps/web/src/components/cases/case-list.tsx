"use client";

import Link from "next/link";
import { useState } from "react";
import { Plus } from "lucide-react";
import { useCases } from "@/lib/queries";
import { PRIORITY_STYLE } from "@/lib/labels";
import { formatRelative } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CaseStatusChip, DemoBadge } from "@/components/shared/badges";
import { FilterBar, FilterSelect, SearchInput } from "@/components/shared/filter-bar";
import { Mono } from "@/components/shared/mono";
import { PageHeader } from "@/components/shared/page-header";
import { Pagination } from "@/components/shared/pagination";
import { EmptyState, QueryState } from "@/components/shared/states";
import { CreateCaseDialog } from "./create-case-dialog";
import { cn } from "@/lib/utils";

const STATUSES = ["DRAFT", "ACTIVE", "PAUSED", "COMPLETED", "ARCHIVED"];
const PAGE_SIZE = 50;

export function CaseList() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [archived, setArchived] = useState(false);
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const query = useCases({ q, status, include_archived: archived, page, page_size: PAGE_SIZE });
  const hasFilters = !!(q || status);

  return (
    <div>
      <PageHeader title="Cases" subtitle="Each case holds targets, investigations and the evidence they produce." actions={<Button size="sm" onClick={() => setCreateOpen(true)}><Plus /> New case</Button>} />
      <FilterBar showClear={hasFilters} onClear={() => { setQ(""); setStatus(""); setPage(1); }}>
        <SearchInput value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search cases…" />
        <FilterSelect value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={STATUSES} placeholder="All statuses" className="w-40" />
        <label className="flex items-center gap-2 text-xs text-fg-muted">
          <Checkbox checked={archived} onCheckedChange={(v) => { setArchived(v === true); setPage(1); }} /> Include archived
        </label>
      </FilterBar>
      <QueryState
        query={query}
        isEmpty={(d) => d.items.length === 0}
        empty={<EmptyState title={hasFilters ? "No cases match" : "No cases yet"} description={hasFilters ? "Try another search or status." : "Create your first case to start collecting public evidence."} action={!hasFilters ? <Button size="sm" onClick={() => setCreateOpen(true)}><Plus /> New case</Button> : undefined} />}
      >
        {(data) => (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead className="w-[32%]">Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead className="text-right">Evidence</TableHead>
                  <TableHead className="text-right">Sources</TableHead>
                  <TableHead className="text-right">Entities</TableHead>
                  <TableHead className="text-right">Findings</TableHead>
                  <TableHead>Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell><Link href={`/cases/${c.id}`}><Mono className="text-fg-muted hover:text-fg">{c.display_id}</Mono></Link></TableCell>
                    <TableCell>
                      <Link href={`/cases/${c.id}`} className="flex items-center gap-2 text-fg hover:text-accent-bright">
                        <span className="truncate font-medium">{c.name}</span>
                        <DemoBadge show={c.is_demo} />
                      </Link>
                      {c.objective ? <p className="truncate text-xs text-fg-subtle">{c.objective}</p> : null}
                    </TableCell>
                    <TableCell><CaseStatusChip value={c.status} /></TableCell>
                    <TableCell><span className={cn("text-xs font-medium", PRIORITY_STYLE[c.priority])}>{c.priority}</span></TableCell>
                    <TableCell className="text-right font-mono text-xs">{c.evidence_count}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{c.source_count}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{c.entity_count}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{c.finding_count}</TableCell>
                    <TableCell className="text-xs text-fg-muted">{formatRelative(c.updated_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
          </>
        )}
      </QueryState>
      <CreateCaseDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
