import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/page-header";
import { PlannedTable } from "@/components/shared/planned-table";

export const metadata = { title: "Monitoring" };

export default function MonitoringPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Monitoring" subtitle="Scheduled re-collection of sources and alerts when public records change." />
      <p className="rounded-md border border-border bg-panel px-4 py-3 text-sm text-fg-muted">
        Monitoring rules, scheduled watches and alert delivery arrive in a later phase. The layout below shows what will be here; nothing is being watched yet.
      </p>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Watches</CardTitle></CardHeader>
          <CardContent className="p-0"><PlannedTable columns={["Case", "Target / source", "Interval", "Last run", "Status"]} message="No watches configured. Watch creation arrives with the Monitoring phase." /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Alerts</CardTitle></CardHeader>
          <CardContent className="p-0"><PlannedTable columns={["Time", "Case", "Kind", "Summary", "Read"]} message="No alerts yet. Alerts appear here when a watched source changes." /></CardContent>
        </Card>
      </div>
    </div>
  );
}
