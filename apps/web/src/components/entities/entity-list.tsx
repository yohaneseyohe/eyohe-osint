"use client";

import { useState } from "react";
import { Crosshair } from "lucide-react";
import { useEntitiesList } from "@/lib/queries";
import type { EntityOut } from "@/lib/types";
import { formatTs } from "@/lib/format";
import { ConfidenceBadge, DemoBadge } from "@/components/shared/badges";
import { FilterBar, SearchInput } from "@/components/shared/filter-bar";
import { Mono } from "@/components/shared/mono";
import { Pagination } from "@/components/shared/pagination";
import { EmptyState, QueryState } from "@/components/shared/states";
import { EntityDrawer } from "./entity-drawer";
import { ENTITY_TYPES, EntityIcon } from "./entity-icon";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 100;

export function EntityList({ caseId }: { caseId: string }) {
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<string | null>(null);
  const query = useEntitiesList(caseId, { q, type, page, page_size: PAGE_SIZE });
  const hasFilters = !!(q || type);

  return (
    <div>
      <FilterBar showClear={hasFilters} onClear={() => { setQ(""); setType(""); setPage(1); }}>
        <SearchInput value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search entities…" />
      </FilterBar>
      <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Filter by entity type">
        {ENTITY_TYPES.map((t) => (
          <button
            key={t}
            onClick={() => { setType(type === t ? "" : t); setPage(1); }}
            aria-pressed={type === t}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase transition-colors",
              type === t ? "border-accent bg-accent-soft text-accent-bright" : "border-border text-fg-muted hover:border-border-strong hover:text-fg",
            )}
          >
            <EntityIcon type={t} className="size-3" /> {t}
          </button>
        ))}
      </div>
      <QueryState
        query={query}
        isEmpty={(d) => d.items.length === 0}
        empty={<EmptyState title={hasFilters ? "No entities match" : "No entities extracted yet"} description={hasFilters ? "Try another type or search term." : "Entities are extracted from evidence as collectors run."} />}
      >
        {(data) => {
          const groups = new Map<string, EntityOut[]>();
          for (const e of data.items) groups.set(e.type, [...(groups.get(e.type) ?? []), e]);
          return (
            <>
              <div className="space-y-5">
                {[...groups.entries()].map(([t, items]) => (
                  <section key={t}>
                    <h3 className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                      <EntityIcon type={t} className="size-3.5" /> {t} <span className="font-mono text-fg-subtle">{items.length}</span>
                    </h3>
                    <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                      {items.map((e) => (
                        <li key={e.id}>
                          <button
                            onClick={() => setOpenId(e.id)}
                            className={cn(
                              "glass flex w-full flex-col gap-1.5 rounded-lg border px-3 py-2.5 text-left transition-colors hover:border-border-strong",
                              e.is_target ? "border-accent/50" : "border-border",
                            )}
                          >
                            <div className="flex items-center gap-2">
                              {e.is_target ? <Crosshair className="size-3.5 text-accent-bright" aria-label="Target" /> : null}
                              <Mono className="truncate text-sm text-fg">{e.value}</Mono>
                              <DemoBadge show={e.is_demo} className="ml-auto" />
                            </div>
                            {e.label && e.label !== e.value ? <p className="truncate text-xs text-fg-muted">{e.label}</p> : null}
                            <div className="flex items-center gap-2 text-[11px] text-fg-subtle">
                              <ConfidenceBadge value={e.confidence} />
                              <span className="font-mono">{e.source_count} src</span>
                              <span className="ml-auto font-mono">{formatTs(e.last_seen).slice(0, 10)}</span>
                            </div>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
              <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
            </>
          );
        }}
      </QueryState>
      <EntityDrawer entityId={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}
