"use client";

import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { humanize } from "@/lib/utils";

export const ALL = "__all__";

export function FilterBar({ children, onClear, showClear }: { children: React.ReactNode; onClear?: () => void; showClear?: boolean }) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      {children}
      {showClear && onClear ? (
        <Button variant="ghost" size="sm" onClick={onClear}>
          <X /> Clear
        </Button>
      ) : null}
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder, className }: { value: string; onChange: (v: string) => void; placeholder?: string; className?: string }) {
  return (
    <div className={`relative ${className ?? "w-64"}`}>
      <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" />
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder ?? "Search…"} className="pl-8" aria-label={placeholder ?? "Search"} />
    </div>
  );
}

export function FilterSelect({
  value,
  onChange,
  options,
  placeholder,
  className,
  format = humanize,
}: {
  value: string;
  onChange: (v: string) => void;
  options: readonly string[];
  placeholder: string;
  className?: string;
  format?: (v: string) => string;
}) {
  return (
    <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? "" : v)}>
      <SelectTrigger className={className ?? "w-44"} aria-label={placeholder}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{placeholder}</SelectItem>
        {options.map((o) => (
          <SelectItem key={o} value={o}>
            {format(o)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
