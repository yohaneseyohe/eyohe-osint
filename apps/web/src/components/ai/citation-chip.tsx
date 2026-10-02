"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

const KIND_STYLE: Record<string, string> = {
  evidence: "border-info/40 text-accent-bright hover:bg-info/10",
  finding: "border-success/40 text-success hover:bg-success/10",
  entity: "border-warning/40 text-warning hover:bg-warning/10",
  snapshot: "border-teal/40 text-teal hover:bg-teal/10",
  note: "border-border text-fg-muted",
};

/** A cited ref (display id) rendered as a chip; the parent decides what opening it does. */
export function CitationChip({ refId, kind, onOpen, className }: { refId: string; kind: string; onOpen: (ref: string, kind: string) => void; className?: string }) {
  const base = cn("inline-flex items-center rounded border px-1 py-px font-mono text-[10px] leading-tight align-baseline transition-colors", KIND_STYLE[kind] ?? KIND_STYLE.note, className);
  if (kind === "finding") return <Link href={`/findings/${refId}`} className={base}>{refId}</Link>;
  if (kind === "note") return <span className={base}>{refId}</span>;
  return <button type="button" onClick={() => onOpen(refId, kind)} className={base}>{refId}</button>;
}
