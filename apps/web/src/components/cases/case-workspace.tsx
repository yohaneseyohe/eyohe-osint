"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { useCase } from "@/lib/queries";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CaseStatusChip, DemoBadge } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorState, LoadingState } from "@/components/shared/states";
import { EvidenceTable } from "@/components/evidence/evidence-table";
import { EntityList } from "@/components/entities/entity-list";
import { CaseGraph } from "@/components/graph/case-graph";
import { TimelineList } from "@/components/timeline/timeline-list";
import { SourceTable } from "@/components/sources/source-table";
import { FindingList } from "@/components/findings/finding-list";
import { AiAnalystPanel } from "./ai-analyst-panel";
import { CaseNotes } from "./case-notes";
import { CaseOverview } from "./case-overview";

const TABS = ["overview", "evidence", "entities", "graph", "timeline", "sources", "findings", "notes", "analyst"] as const;
type Tab = (typeof TABS)[number];

export function CaseWorkspace({ id }: { id: string }) {
  const query = useCase(id);
  const router = useRouter();
  const params = useSearchParams();
  const tabParam = params.get("tab");
  const tab: Tab = TABS.includes(tabParam as Tab) ? (tabParam as Tab) : "overview";

  if (query.isPending) return <LoadingState rows={8} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  const c = query.data;

  return (
    <div>
      <PageHeader
        title={<><Mono className="text-fg-subtle">{c.display_id}</Mono>{c.name}<CaseStatusChip value={c.status} /><DemoBadge show={c.is_demo} /></>}
        subtitle={
          <span className="flex items-center gap-3">
            <Link href="/cases" className="inline-flex items-center gap-1 text-accent-bright hover:underline"><ArrowLeft className="size-3" /> All cases</Link>
            <span className="font-mono">{c.evidence_count} evidence · {c.source_count} sources · {c.entity_count} entities · {c.finding_count} findings</span>
          </span>
        }
      />
      <Tabs value={tab} onValueChange={(v) => router.replace(`/cases/${id}?tab=${v}`, { scroll: false })}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="evidence">Evidence <Mono className="text-fg-subtle">{c.evidence_count}</Mono></TabsTrigger>
          <TabsTrigger value="entities">Entities <Mono className="text-fg-subtle">{c.entity_count}</Mono></TabsTrigger>
          <TabsTrigger value="graph">Graph</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="sources">Sources <Mono className="text-fg-subtle">{c.source_count}</Mono></TabsTrigger>
          <TabsTrigger value="findings">Findings <Mono className="text-fg-subtle">{c.finding_count}</Mono></TabsTrigger>
          <TabsTrigger value="notes">Notes</TabsTrigger>
          <TabsTrigger value="analyst">AI Analyst</TabsTrigger>
        </TabsList>
        <TabsContent value="overview"><CaseOverview c={c} /></TabsContent>
        <TabsContent value="evidence"><EvidenceTable caseId={c.id} /></TabsContent>
        <TabsContent value="entities"><EntityList caseId={c.id} /></TabsContent>
        <TabsContent value="graph">{tab === "graph" ? <CaseGraph caseId={c.id} /> : null}</TabsContent>
        <TabsContent value="timeline"><TimelineList caseId={c.id} /></TabsContent>
        <TabsContent value="sources"><SourceTable caseId={c.id} /></TabsContent>
        <TabsContent value="findings"><FindingList caseId={c.id} /></TabsContent>
        <TabsContent value="notes"><CaseNotes caseId={c.id} /></TabsContent>
        <TabsContent value="analyst"><AiAnalystPanel c={c} /></TabsContent>
      </Tabs>
    </div>
  );
}
