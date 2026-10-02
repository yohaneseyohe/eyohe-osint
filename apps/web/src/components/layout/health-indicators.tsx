"use client";

import Link from "next/link";
import { useHealth } from "@/lib/queries";
import { HEALTH_STYLE } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { SimpleTooltip } from "@/components/ui/tooltip";

const SHOWN: { key: string; label: string }[] = [
  { key: "api", label: "API" },
  { key: "database", label: "DB" },
  { key: "ollama", label: "Ollama" },
  { key: "internet", label: "Internet" },
  { key: "search", label: "Search" },
];

/** Compact system health dots in the top bar, polled from /health every 30s. */
export function HealthIndicators() {
  const health = useHealth(30_000);
  const byName = new Map(health.data?.components.map((c) => [c.name, c]) ?? []);
  return (
    <Link href="/settings?tab=health" className="flex items-center gap-3 rounded-md px-2 py-1 hover:bg-panel-2" aria-label="System health">
      {SHOWN.map(({ key, label }) => {
        const c = byName.get(key);
        const status = health.isError ? (key === "api" ? "OFFLINE" : "NOT_CONFIGURED") : c?.status ?? "NOT_CONFIGURED";
        const style = HEALTH_STYLE[status] ?? HEALTH_STYLE.NOT_CONFIGURED;
        const tip = health.isError
          ? "API unreachable"
          : c
            ? `${label}: ${status}${c.message ? ` — ${c.message}` : ""}${c.latency_ms != null ? ` (${c.latency_ms} ms)` : ""}`
            : `${label}: not reported`;
        return (
          <SimpleTooltip key={key} content={tip}>
            <span className="flex items-center gap-1.5 text-[11px] text-fg-muted">
              <span className={cn("size-2 rounded-full", style.dot, health.isPending && "animate-pulse")} aria-hidden />
              <span className="hidden xl:inline">{label}</span>
              <span className="sr-only">{tip}</span>
            </span>
          </SimpleTooltip>
        );
      })}
    </Link>
  );
}
