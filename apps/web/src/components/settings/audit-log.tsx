"use client";

import { useState } from "react";
import { useAudit } from "@/lib/queries";
import { formatTs } from "@/lib/format";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { FilterBar, SearchInput } from "@/components/shared/filter-bar";
import { Mono } from "@/components/shared/mono";
import { Pagination } from "@/components/shared/pagination";
import { EmptyState, QueryState } from "@/components/shared/states";
import { TypeChip } from "@/components/shared/badges";

const PAGE_SIZE = 100;

export function AuditLog() {
  const [action, setAction] = useState("");
  const [caseId, setCaseId] = useState("");
  const [page, setPage] = useState(1);
  const query = useAudit({ action: action.trim(), case_id: caseId.trim(), page, page_size: PAGE_SIZE });
  const hasFilters = !!(action || caseId);
  return (
    <div>
      <FilterBar showClear={hasFilters} onClear={() => { setAction(""); setCaseId(""); setPage(1); }}>
        <SearchInput value={action} onChange={(v) => { setAction(v); setPage(1); }} placeholder="Action (exact, e.g. CASE_CREATED)" className="w-72" />
        <SearchInput value={caseId} onChange={(v) => { setCaseId(v); setPage(1); }} placeholder="Case UUID" className="w-80" />
      </FilterBar>
      <QueryState query={query} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title={hasFilters ? "No audit entries match" : "Audit log is empty"} description="Every mutation, review and configuration change is recorded here." />}>
        {(data) => (
          <>
            <Table>
              <TableHeader>
                <TableRow><TableHead>Time</TableHead><TableHead>Actor</TableHead><TableHead>Action</TableHead><TableHead>Object</TableHead><TableHead>Case</TableHead><TableHead>Detail</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell><Mono className="text-fg-subtle">{formatTs(a.created_at)}</Mono></TableCell>
                    <TableCell className="text-xs text-fg">{a.actor}</TableCell>
                    <TableCell><TypeChip value={a.action} /></TableCell>
                    <TableCell><Mono className="text-fg-muted">{a.object_type ? `${a.object_type}:${(a.object_id ?? "").slice(0, 8)}` : "—"}</Mono></TableCell>
                    <TableCell><Mono className="text-fg-subtle">{a.case_id ? a.case_id.slice(0, 8) : "—"}</Mono></TableCell>
                    <TableCell className="max-w-md"><Mono className="block truncate text-fg-subtle" title={a.detail ? JSON.stringify(a.detail) : ""}>{a.detail && Object.keys(a.detail).length > 0 ? JSON.stringify(a.detail) : "—"}</Mono></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
          </>
        )}
      </QueryState>
    </div>
  );
}
