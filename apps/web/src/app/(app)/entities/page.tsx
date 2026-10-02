"use client";

import { CasePicker, useSelectedCaseId } from "@/components/shared/case-picker";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { EntityList } from "@/components/entities/entity-list";

export default function EntitiesPage() {
  const caseId = useSelectedCaseId();
  return (
    <div>
      <PageHeader title="Entities" subtitle="People, accounts, infrastructure and documents extracted from evidence." actions={<CasePicker />} />
      {caseId ? <EntityList caseId={caseId} /> : <EmptyState title="Select a case to browse its entities" />}
    </div>
  );
}
