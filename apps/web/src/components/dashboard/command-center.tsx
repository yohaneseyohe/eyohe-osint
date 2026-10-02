"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { useDashboard } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorState } from "@/components/shared/states";
import { NewInvestigationDialog } from "@/components/layout/new-investigation-dialog";
import { ConfidenceBreakdown, EntityOverview, SourceDistributionChart } from "./charts";
import { ActiveInvestigations, LiveCollectionFeed, RecentFindings } from "./lists";
import { StatTiles } from "./stat-tiles";

function Panel({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-3">{children}</CardContent>
    </Card>
  );
}

export function CommandCenter() {
  const dash = useDashboard();
  const [newOpen, setNewOpen] = useState(false);
  const d = dash.data;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Command Center"
        subtitle="Live overview of every case, investigation and collection on this workstation."
        actions={
          <Button size="sm" onClick={() => setNewOpen(true)}>
            <Plus /> New Investigation
          </Button>
        }
      />
      {dash.isError ? <ErrorState error={dash.error} onRetry={() => dash.refetch()} /> : null}
      <StatTiles data={d} />
      <div className="grid gap-4 xl:grid-cols-3">
        <Panel title="Active investigations" className="xl:col-span-2">
          {d ? <ActiveInvestigations items={d.active_investigations} onNew={() => setNewOpen(true)} /> : <Skeleton className="h-32" />}
        </Panel>
        <Panel title="Recent findings">{d ? <RecentFindings items={d.recent_findings} /> : <Skeleton className="h-32" />}</Panel>
        <Panel title="Live collection feed" className="xl:col-span-2">
          {d ? <LiveCollectionFeed items={d.recent_events} /> : <Skeleton className="h-48" />}
        </Panel>
        <Panel title="Source distribution">{d ? <SourceDistributionChart data={d.source_distribution} /> : <Skeleton className="h-40" />}</Panel>
        <Panel title="Finding confidence">{d ? <ConfidenceBreakdown data={d.finding_confidence} /> : <Skeleton className="h-40" />}</Panel>
        <Panel title="Entity overview" className="xl:col-span-2">
          {d ? <EntityOverview data={d.entity_types} /> : <Skeleton className="h-40" />}
        </Panel>
      </div>
      <NewInvestigationDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  );
}
