"use client";

import { useSearchParams } from "next/navigation";
import { CasePicker, useSelectedCaseId } from "@/components/shared/case-picker";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { EvidenceTable } from "./evidence-table";

export function EvidencePage() {
  const caseId = useSelectedCaseId();
  const params = useSearchParams();
  return (
    <div>
      <PageHeader title="Evidence" subtitle="Every claim Eyohe records, tied to its source snapshot and open to review." actions={<CasePicker />} />
      {caseId ? <EvidenceTable caseId={caseId} initialEvidenceId={params.get("open")} /> : <EmptyState title="Select a case to browse its evidence" description="Create a case first if the list is empty." />}
    </div>
  );
}
