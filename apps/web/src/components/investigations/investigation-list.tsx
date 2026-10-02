"use client";

import Link from "next/link";
import { useState } from "react";
import { Plus } from "lucide-react";
import { useInvestigations } from "@/lib/queries";
import { formatRelative, formatTs } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { InvestigationStatusChip } from "@/components/shared/badges";
import { FilterBar, FilterSelect } from "@/components/shared/filter-bar";
import { Mono } from "@/components/shared/mono";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, QueryState } from "@/components/shared/states";
import { NewInvestigationDialog } from "@/components/layout/new-investigation-dialog";

const STATUSES = ["DRAFT", "PLANNING", "AWAITING_APPROVAL", "RUNNING", "PAUSED", "VERIFYING", "COMPLETED", "STOPPED", "FAILED"];

export function InvestigationList() {
  const [status, setStatus] = useState("");
  const [newOpen, setNewOpen] = useState(false);
  const query = useInvestigations({ status });
  return (
    <div>
      <PageHeader title="Investigations" subtitle="Planned, running and finished collection runs across all cases." actions={<Button size="sm" onClick={() => setNewOpen(true)}><Plus /> New Investigation</Button>} />
      <FilterBar showClear={!!status} onClear={() => setStatus("")}>
        <FilterSelect value={status} onChange={setStatus} options={STATUSES} placeholder="All statuses" className="w-48" />
      </FilterBar>
      <QueryState query={query} isEmpty={(d) => d.length === 0} empty={<EmptyState title={status ? "No investigations with this status" : "No investigations yet — start one"} action={!status ? <Button size="sm" onClick={() => setNewOpen(true)}><Plus /> New Investigation</Button> : undefined} />}>
        {(items) => (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead className="w-[36%]">Name / request</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Plan</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((i) => (
                <TableRow key={i.id}>
                  <TableCell><Link href={`/investigations/${i.id}`}><Mono className="text-fg-muted hover:text-fg">{i.display_id}</Mono></Link></TableCell>
                  <TableCell>
                    <Link href={`/investigations/${i.id}`} className="block truncate font-medium text-fg hover:text-accent-bright">{i.name || i.request_text || i.objective || "Investigation"}</Link>
                    <Link href={`/cases/${i.case_id}`} className="font-mono text-[10px] text-fg-subtle hover:text-fg">case {i.case_id.slice(0, 8)}</Link>
                  </TableCell>
                  <TableCell><InvestigationStatusChip value={i.status} /></TableCell>
                  <TableCell className="text-xs text-fg-muted">{i.plan_source}</TableCell>
                  <TableCell><Mono className="text-fg-subtle">{i.started_at ? formatTs(i.started_at) : "—"}</Mono></TableCell>
                  <TableCell className="text-xs text-fg-muted">{formatRelative(i.updated_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </QueryState>
      <NewInvestigationDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  );
}
