"use client";

import { useCollectors } from "@/lib/queries";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { HealthChip, StageChip, TierBadge, TypeChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { EmptyState, QueryState } from "@/components/shared/states";

export function CollectorsTab() {
  const q = useCollectors();
  return (
    <QueryState query={q} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No collectors registered" description="Collectors are registered by the API at startup; none are available in this build yet." />}>
      {(items) => (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Collector</TableHead>
              <TableHead>Stage</TableHead>
              <TableHead>Targets</TableHead>
              <TableHead>Tier</TableHead>
              <TableHead>Internet</TableHead>
              <TableHead>Health</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((c) => (
              <TableRow key={c.name}>
                <TableCell>
                  <Mono className="text-fg">{c.name}</Mono>
                  <p className="text-xs text-fg-muted">{c.description}</p>
                </TableCell>
                <TableCell><StageChip value={c.stage} /></TableCell>
                <TableCell><div className="flex flex-wrap gap-1">{c.targets.map((t) => <TypeChip key={t} value={t} />)}</div></TableCell>
                <TableCell><TierBadge tier={c.tier} /></TableCell>
                <TableCell className="text-xs text-fg-muted">{c.requires_internet ? "required" : "offline"}</TableCell>
                <TableCell>
                  {c.health ? (
                    <div className="space-y-0.5">
                      <HealthChip value={c.health.status} />
                      {c.health.message ? <p className="text-[11px] text-fg-muted">{c.health.message}</p> : null}
                    </div>
                  ) : <span className="text-xs text-fg-subtle">not reported</span>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </QueryState>
  );
}
