"use client";

import { useState } from "react";
import { useSourcesList } from "@/lib/queries";
import { SOURCE_TYPES } from "@/lib/labels";
import { formatDate, formatTs } from "@/lib/format";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DemoBadge, TierBadge, TypeChip } from "@/components/shared/badges";
import { FilterBar, FilterSelect, SearchInput } from "@/components/shared/filter-bar";
import { Mono } from "@/components/shared/mono";
import { Pagination } from "@/components/shared/pagination";
import { EmptyState, QueryState } from "@/components/shared/states";
import { SourceDrawer } from "./source-drawer";
import { truncate } from "@/lib/utils";

const PAGE_SIZE = 50;
const TIERS = ["1", "2", "3", "4", "5"];

export function SourceTable({ caseId }: { caseId: string }) {
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [maxTier, setMaxTier] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<string | null>(null);
  const query = useSourcesList(caseId, { q, source_type: type, max_tier: maxTier, page, page_size: PAGE_SIZE });
  const hasFilters = !!(q || type || maxTier);

  return (
    <div>
      <FilterBar showClear={hasFilters} onClear={() => { setQ(""); setType(""); setMaxTier(""); setPage(1); }}>
        <SearchInput value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search title, URL, domain…" />
        <FilterSelect value={type} onChange={(v) => { setType(v); setPage(1); }} options={SOURCE_TYPES} placeholder="All source types" />
        <FilterSelect value={maxTier} onChange={(v) => { setMaxTier(v); setPage(1); }} options={TIERS} placeholder="Any tier" format={(v) => `Tier ${v} or better`} className="w-40" />
      </FilterBar>
      <QueryState
        query={query}
        isEmpty={(d) => d.items.length === 0}
        empty={<EmptyState title={hasFilters ? "No sources match" : "No sources collected yet"} description={hasFilters ? "Try clearing a filter." : "Each fetched page, record or post becomes a source with a stored snapshot."} />}
      >
        {(data) => (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead className="w-[38%]">Title / URL</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Domain</TableHead>
                  <TableHead>Tier</TableHead>
                  <TableHead>Collector</TableHead>
                  <TableHead>Published</TableHead>
                  <TableHead>Collected</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((s) => (
                  <TableRow key={s.id} className="cursor-pointer" onClick={() => setOpenId(s.id)} tabIndex={0} onKeyDown={(ev) => ev.key === "Enter" && setOpenId(s.id)}>
                    <TableCell><Mono className="text-fg-muted">{s.display_id}</Mono></TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="truncate text-fg">{s.title || "(untitled)"}</span>
                        <DemoBadge show={s.is_demo} />
                      </div>
                      <Mono className="block truncate text-fg-subtle">{truncate(s.url, 90)}</Mono>
                    </TableCell>
                    <TableCell><TypeChip value={s.source_type} /></TableCell>
                    <TableCell><Mono className="text-fg-muted">{s.domain}</Mono></TableCell>
                    <TableCell><TierBadge tier={s.tier} /></TableCell>
                    <TableCell><Mono className="text-fg-muted">{s.collector || "—"}</Mono></TableCell>
                    <TableCell><Mono className="text-fg-subtle">{s.published_at ? formatDate(s.published_at) : "—"}</Mono></TableCell>
                    <TableCell><Mono className="text-fg-subtle">{formatTs(s.collected_at)}</Mono></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
          </>
        )}
      </QueryState>
      <SourceDrawer sourceId={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}
