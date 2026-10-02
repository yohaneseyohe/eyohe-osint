"use client";

import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CONFIDENCE_ORDER, CONFIDENCE_STYLE, ENTITY_TYPE_COLOR } from "@/lib/labels";
import { humanize } from "@/lib/utils";
import { EmptyState } from "@/components/shared/states";

const SOURCE_COLORS = ["#60a5fa", "#14b8a6", "#a78bfa", "#f59e0b", "#38bdf8", "#34d399", "#f472b6", "#94a3b8", "#fbbf24", "#2dd4bf", "#e2e8f0"];

const tooltipStyle = {
  contentStyle: { background: "var(--panel-2)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 12 },
  itemStyle: { color: "var(--fg)" },
  labelStyle: { color: "var(--fg-muted)" },
  cursor: { fill: "rgba(96,165,250,0.08)" },
};

export function SourceDistributionChart({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data)
    .map(([name, value]) => ({ name: humanize(name), value }))
    .sort((a, b) => b.value - a.value);
  if (rows.length === 0) return <EmptyState title="No sources collected yet" description="Source types appear here after the first collection run." className="py-8" />;
  const total = rows.reduce((a, r) => a + r.value, 0);
  return (
    <div className="flex items-center gap-4">
      <div className="h-40 w-40 shrink-0">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={rows} dataKey="value" nameKey="name" innerRadius={44} outerRadius={70} paddingAngle={2} stroke="var(--panel)">
              {rows.map((_, i) => (
                <Cell key={i} fill={SOURCE_COLORS[i % SOURCE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip {...tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="min-w-0 flex-1 space-y-1 text-xs">
        {rows.map((r, i) => (
          <li key={r.name} className="flex items-center gap-2">
            <span className="size-2 rounded-sm" style={{ background: SOURCE_COLORS[i % SOURCE_COLORS.length] }} aria-hidden />
            <span className="truncate text-fg-muted">{r.name}</span>
            <span className="ml-auto font-mono text-fg">{r.value}</span>
            <span className="w-10 text-right font-mono text-fg-subtle">{Math.round((100 * r.value) / total)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ConfidenceBreakdown({ data }: { data: Record<string, number> }) {
  const rows = CONFIDENCE_ORDER.map((c) => ({ name: c, value: data[c] ?? 0 })).filter((r) => r.value > 0);
  if (rows.length === 0) return <EmptyState title="No findings yet" description="Confidence levels are computed from evidence once findings exist." className="py-8" />;
  return (
    <div className="h-44">
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
          <XAxis type="number" hide allowDecimals={false} />
          <YAxis type="category" dataKey="name" width={100} tick={{ fill: "var(--fg-muted)", fontSize: 11, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} />
          <Tooltip {...tooltipStyle} />
          <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={14}>
            {rows.map((r) => (
              <Cell key={r.name} fill={CONFIDENCE_STYLE[r.name].color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function EntityOverview({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data).sort((a, b) => b[1] - a[1]);
  if (rows.length === 0) return <EmptyState title="No entities yet" description="Entities are extracted from evidence during investigations." className="py-8" />;
  const max = Math.max(...rows.map(([, n]) => n));
  return (
    <ul className="space-y-1.5">
      {rows.map(([type, n]) => (
        <li key={type} className="flex items-center gap-3 text-xs">
          <span className="w-28 truncate font-mono text-[10px] uppercase text-fg-muted">{type}</span>
          <div className="h-1.5 flex-1 rounded-full bg-panel-2">
            <div className="h-full rounded-full" style={{ width: `${(100 * n) / max}%`, background: ENTITY_TYPE_COLOR[type] ?? "var(--slate)" }} />
          </div>
          <span className="w-8 text-right font-mono text-fg">{n}</span>
        </li>
      ))}
    </ul>
  );
}
