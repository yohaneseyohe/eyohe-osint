"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { useFindingsList } from "@/lib/queries";
import { CONFIDENCE_ORDER, REVIEW_ORDER } from "@/lib/labels";
import { formatRelative } from "@/lib/format";
import { ConfidenceBadge, DemoBadge, ReviewChip, TypeChip } from "@/components/shared/badges";
import { FilterBar, FilterSelect } from "@/components/shared/filter-bar";
import { Mono } from "@/components/shared/mono";
import { Pagination } from "@/components/shared/pagination";
import { EmptyState, QueryState } from "@/components/shared/states";

const PAGE_SIZE = 50;

export function FindingList({ caseId }: { caseId: string }) {
  const [confidence, setConfidence] = useState("");
  const [review, setReview] = useState("");
  const [page, setPage] = useState(1);
  const query = useFindingsList(caseId, { confidence, review_state: review, page, page_size: PAGE_SIZE });
  const hasFilters = !!(confidence || review);
  return (
    <div>
      <FilterBar showClear={hasFilters} onClear={() => { setConfidence(""); setReview(""); setPage(1); }}>
        <FilterSelect value={confidence} onChange={(v) => { setConfidence(v); setPage(1); }} options={CONFIDENCE_ORDER} placeholder="All confidence" format={(v) => v} />
        <FilterSelect value={review} onChange={(v) => { setReview(v); setPage(1); }} options={REVIEW_ORDER} placeholder="All review states" />
      </FilterBar>
      <QueryState query={query} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title={hasFilters ? "No findings match" : "No findings yet"} description={hasFilters ? "Try clearing a filter." : "Findings are drafted from collected evidence during verification; every claim cites evidence IDs."} />}>
        {(data) => (
          <>
            <ul className="space-y-2">
              {data.items.map((f) => (
                <li key={f.id}>
                  <Link href={`/findings/${f.id}`} className="glass flex items-start gap-3 rounded-lg border border-border px-4 py-3 transition-colors hover:border-border-strong">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Mono className="text-fg-subtle">{f.display_id}</Mono>
                        <span className="text-sm font-medium text-fg">{f.title}</span>
                        <DemoBadge show={f.is_demo} />
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-fg-muted">{f.claim}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-fg-subtle">
                        <TypeChip value={f.category} />
                        <span>severity {f.severity}</span>
                        <span>· proposed by {f.proposed_by}</span>
                        <span>· {formatRelative(f.updated_at)}</span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1.5">
                      <ConfidenceBadge value={f.confidence} />
                      <ReviewChip value={f.review_state} />
                    </div>
                    <ArrowRight className="mt-1 size-4 text-fg-subtle" />
                  </Link>
                </li>
              ))}
            </ul>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
          </>
        )}
      </QueryState>
    </div>
  );
}
