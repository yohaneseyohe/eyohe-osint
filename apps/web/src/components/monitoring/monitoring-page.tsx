"use client";

import { CasePicker, useSelectedCaseId } from "@/components/shared/case-picker";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { AlertsList } from "./alerts-list";
import { MonitorsTable } from "./monitors-table";

export function MonitoringPage() {
  const caseId = useSelectedCaseId();
  return (
    <div className="space-y-4">
      <PageHeader title="Monitoring" subtitle="Scheduled re-collection of public sources and alerts when records change." actions={<CasePicker />} />
      {caseId ? <MonitorsTable key={caseId} caseId={caseId} /> : <EmptyState title="Select a case to manage its monitors" />}
      <AlertsList caseId={caseId} />
    </div>
  );
}
