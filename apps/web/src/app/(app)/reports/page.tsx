import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";
import { PlannedTable } from "@/components/shared/planned-table";

export const metadata = { title: "Reports" };

export default function ReportsPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Reports" subtitle="Exportable case reports where every statement cites evidence IDs and source URLs." />
      <p className="rounded-md border border-border bg-panel px-4 py-3 text-sm text-fg-muted">
        Report generation (Markdown, PDF, JSON evidence bundles) arrives in a later phase. Reports will be built only from accepted and pending evidence; rejected items are excluded automatically.
      </p>
      <Card>
        <CardHeader><CardTitle>Generated reports</CardTitle></CardHeader>
        <CardContent className="p-0"><PlannedTable columns={["ID", "Case", "Format", "Classification", "Generated", "Evidence cited", "Download"]} message="No reports generated yet." /></CardContent>
      </Card>
    </div>
  );
}
