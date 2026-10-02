"use client";

import { useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { useUiStore } from "@/lib/store";
import { CasePicker, useSelectedCaseId } from "@/components/shared/case-picker";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { CaseGraph } from "./case-graph";

export function GraphPage() {
  const params = useSearchParams();
  const setSelected = useUiStore((s) => s.setSelectedCaseId);
  const caseFromUrl = params.get("case");
  useEffect(() => {
    if (caseFromUrl) setSelected(caseFromUrl);
  }, [caseFromUrl, setSelected]);
  const caseId = useSelectedCaseId();
  return (
    <div>
      <PageHeader title="Relationship Graph" subtitle="Every edge is backed by evidence; click one to see why it exists." actions={<CasePicker />} />
      {caseId ? <CaseGraph key={caseId} caseId={caseId} initialEntityId={params.get("entity")} /> : <EmptyState title="Select a case to render its graph" />}
    </div>
  );
}
