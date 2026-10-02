"use client";

import { useEffect } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCases } from "@/lib/queries";
import { useUiStore } from "@/lib/store";
import { Mono } from "./mono";

/**
 * Global case selector used by the case-independent routes (/evidence, /graph, ...).
 * Persists the selection so switching between those routes keeps the same case.
 */
export function CasePicker({ className }: { className?: string }) {
  const cases = useCases({ page_size: 200, include_archived: true });
  const selected = useUiStore((s) => s.selectedCaseId);
  const setSelected = useUiStore((s) => s.setSelectedCaseId);

  useEffect(() => {
    const items = cases.data?.items;
    if (!items || items.length === 0) return;
    if (!selected || !items.some((c) => c.id === selected)) setSelected(items[0].id);
  }, [cases.data, selected, setSelected]);

  const items = cases.data?.items ?? [];
  return (
    <Select value={selected ?? undefined} onValueChange={setSelected} disabled={items.length === 0}>
      <SelectTrigger className={className ?? "w-72"} aria-label="Select case">
        <SelectValue placeholder={cases.isPending ? "Loading cases…" : "No cases yet"} />
      </SelectTrigger>
      <SelectContent>
        {items.map((c) => (
          <SelectItem key={c.id} value={c.id}>
            <span className="flex items-center gap-2">
              <Mono className="text-fg-subtle">{c.display_id}</Mono>
              <span className="truncate">{c.name}</span>
              {c.is_demo ? <span className="text-[10px] text-warning">DEMO</span> : null}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function useSelectedCaseId(): string | null {
  return useUiStore((s) => s.selectedCaseId);
}
