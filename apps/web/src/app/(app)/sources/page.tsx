"use client";

import { CasePicker, useSelectedCaseId } from "@/components/shared/case-picker";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { SourceTable } from "@/components/sources/source-table";

export default function SourcesPage() {
  const caseId = useSelectedCaseId();
  return (
    <div>
      <PageHeader title="Source Explorer" subtitle="Where each piece of evidence came from, with reliability tiers and stored snapshots." actions={<CasePicker />} />
      {caseId ? <SourceTable caseId={caseId} /> : <EmptyState title="Select a case to explore its sources" />}
    </div>
  );
}
