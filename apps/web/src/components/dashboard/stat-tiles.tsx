import Link from "next/link";
import { Activity, Briefcase, Globe, Lightbulb, ShieldCheck, Users } from "lucide-react";
import type { DashboardOut } from "@/lib/types";
import { formatNumber } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";

export function StatTiles({ data }: { data: DashboardOut | undefined }) {
  const active = data
    ? Object.entries(data.investigations.by_status)
        .filter(([s]) => ["RUNNING", "VERIFYING", "PAUSED", "AWAITING_APPROVAL", "PLANNING"].includes(s))
        .reduce((a, [, n]) => a + n, 0)
    : 0;
  const tiles = [
    { label: "Cases", value: data?.cases.total, icon: Briefcase, href: "/cases" },
    { label: "Active investigations", value: active, icon: Activity, href: "/investigations" },
    { label: "Evidence", value: data?.evidence, icon: ShieldCheck, href: "/evidence" },
    { label: "Sources", value: data?.sources, icon: Globe, href: "/sources" },
    { label: "Entities", value: data?.entities, icon: Users, href: "/entities" },
    { label: "Findings", value: data?.findings, icon: Lightbulb, href: "/investigations" },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-6">
      {tiles.map((t) => (
        <Link
          key={t.label}
          href={t.href}
          className="glass group rounded-lg border border-border px-4 py-3 transition-colors hover:border-border-strong"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-fg-muted">{t.label}</span>
            <t.icon className="size-4 text-fg-subtle group-hover:text-accent-bright" />
          </div>
          {data ? (
            <div className="mt-2 font-mono text-2xl font-semibold tabular-nums text-fg">{formatNumber(t.value)}</div>
          ) : (
            <Skeleton className="mt-2 h-8 w-16" />
          )}
        </Link>
      ))}
    </div>
  );
}
