"use client";

import { useState } from "react";
import { useEvidenceList } from "@/lib/queries";
import { CONFIDENCE_ORDER, EVIDENCE_TYPES, REVIEW_ORDER } from "@/lib/labels";
import { formatTs } from "@/lib/format";
import type { EvidenceOut } from "@/lib/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ConfidenceBadge, DemoBadge, ReviewChip, TypeChip } from "@/components/shared/badges";
import { FilterBar, FilterSelect, SearchInput } from "@/components/shared/filter-bar";
import { Mono } from "@/components/shared/mono";
import { Pagination } from "@/components/shared/pagination";
import { EmptyState, QueryState } from "@/components/shared/states";
import { EvidenceReviewDialog } from "./evidence-review-dialog";
import { truncate } from "@/lib/utils";

const PAGE_SIZE = 50;

export interface EvidenceFilters {
  q?: string;
  evidence_type?: string;
  review_state?: string;
  confidence?: string;
  collector?: string;
}

export function EvidenceTable({ caseId, initialEvidenceId, initialFilters }: { caseId: string; initialEvidenceId?: string | null; initialFilters?: EvidenceFilters }) {
  const [q, setQ] = useState(initialFilters?.q ?? "");
  const [type, setType] = useState(initialFilters?.evidence_type ?? "");
  const [review, setReview] = useState(initialFilters?.review_state ?? "");
  const [confidence, setConfidence] = useState(initialFilters?.confidence ?? "");
  const [collector, setCollector] = useState(initialFilters?.collector ?? "");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<string | null>(initialEvidenceId ?? null);
  const params = { q, evidence_type: type, review_state: review, confidence, collector, page, page_size: PAGE_SIZE };
  const query = useEvidenceList(caseId, params);
  const hasFilters = !!(q || type || review || confidence || collector);

  return (
    <div>
      <FilterBar
        showClear={hasFilters}
        onClear={() => {
          setQ("");
          setType("");
          setReview("");
          setConfidence("");
          setCollector("");
          setPage(1);
        }}
      >
        <SearchInput value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search claims and excerpts…" />
        <FilterSelect value={type} onChange={(v) => { setType(v); setPage(1); }} options={EVIDENCE_TYPES} placeholder="All types" />
        <FilterSelect value={review} onChange={(v) => { setReview(v); setPage(1); }} options={REVIEW_ORDER} placeholder="All review states" />
        <FilterSelect value={confidence} onChange={(v) => { setConfidence(v); setPage(1); }} options={CONFIDENCE_ORDER} placeholder="All confidence" format={(v) => v} />
        <SearchInput value={collector} onChange={(v) => { setCollector(v); setPage(1); }} placeholder="Collector…" className="w-40" />
      </FilterBar>
      <QueryState
        query={query}
        isEmpty={(d) => d.items.length === 0}
        empty={
          <EmptyState
            title={hasFilters ? "No evidence matches these filters" : "No evidence collected yet"}
            description={hasFilters ? "Try clearing a filter." : "Evidence is created by collectors during an investigation, each item tied to a source snapshot."}
          />
        }
      >
        {(data) => (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="w-[40%]">Claim</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Review</TableHead>
                  <TableHead>Collector</TableHead>
                  <TableHead>Collected</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((e: EvidenceOut) => (
                  <TableRow key={e.id} className="cursor-pointer" onClick={() => setOpenId(e.id)} tabIndex={0} onKeyDown={(ev) => ev.key === "Enter" && setOpenId(e.id)}>
                    <TableCell>
                      <Mono className="text-fg-muted">{e.display_id}</Mono>
                    </TableCell>
                    <TableCell>
                      <TypeChip value={e.evidence_type} />
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="text-fg">{truncate(e.claim, 140)}</span>
                        <DemoBadge show={e.is_demo} />
                        {e.excerpt_verified ? <span className="text-[10px] text-success" title="Excerpt verified in snapshot">verified</span> : null}
                      </div>
                    </TableCell>
                    <TableCell>
                      <ConfidenceBadge value={e.confidence} />
                    </TableCell>
                    <TableCell>
                      <ReviewChip value={e.review_state} />
                    </TableCell>
                    <TableCell>
                      <Mono className="text-fg-muted">{e.collector || "—"}</Mono>
                    </TableCell>
                    <TableCell>
                      <Mono className="text-fg-subtle">{formatTs(e.collected_at)}</Mono>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
          </>
        )}
      </QueryState>
      <EvidenceReviewDialog evidenceId={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}
