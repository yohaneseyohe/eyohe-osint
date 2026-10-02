"use client";

import { CasePicker, useSelectedCaseId } from "@/components/shared/case-picker";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { ReportsPanel } from "./reports-panel";

export function ReportsPage() {
  const caseId = useSelectedCaseId();
  return (
    <div>
      <PageHeader title="Reports" subtitle="Exportable case reports where every statement cites evidence IDs and source URLs." actions={<CasePicker />} />
      {caseId ? <ReportsPanel key={caseId} caseId={caseId} /> : <EmptyState title="Select a case to generate or download reports" />}
    </div>
  );
}
