import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

/** Table shell for features that ship in a later phase: real headers, honest empty body, no fabricated rows. */
export function PlannedTable({ columns, message }: { columns: string[]; message: string }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>{columns.map((c) => <TableHead key={c}>{c}</TableHead>)}</TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell colSpan={columns.length} className="py-10 text-center text-xs text-fg-subtle">{message}</TableCell>
        </TableRow>
      </TableBody>
    </Table>
  );
}
