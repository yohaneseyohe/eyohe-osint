"use client";

import { CasePicker, useSelectedCaseId } from "@/components/shared/case-picker";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { TimelineList } from "@/components/timeline/timeline-list";

export default function TimelinePage() {
  const caseId = useSelectedCaseId();
  return (
    <div>
      <PageHeader title="Timeline" subtitle="Chronology of dated events reconstructed from evidence." actions={<CasePicker />} />
      {caseId ? <TimelineList caseId={caseId} /> : <EmptyState title="Select a case to view its timeline" />}
    </div>
  );
}
