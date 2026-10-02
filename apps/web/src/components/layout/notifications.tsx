"use client";

import Link from "next/link";
import { Bell, CheckCheck } from "lucide-react";
import { useAlerts } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { AlertRow, useAlertActions } from "@/components/monitoring/alerts-list";
import { Skeleton } from "@/components/ui/skeleton";

export function NotificationsBell() {
  const alerts = useAlerts({ unread: true, page_size: 10 });
  const { ack, readAll } = useAlertActions();
  const unread = alerts.data?.total ?? 0;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon-sm" className="relative" aria-label={`Notifications, ${unread} unread`}>
          <Bell />
          {unread > 0 ? (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 font-mono text-[10px] text-white">
              {unread > 99 ? "99+" : unread}
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-96 p-0">
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-fg-muted">Unread alerts {unread > 0 ? `(${unread})` : ""}</p>
          <Button variant="ghost" size="xs" onClick={() => readAll.mutate(null)} disabled={unread === 0} loading={readAll.isPending}><CheckCheck /> Read all</Button>
        </div>
        {alerts.isPending ? <div className="space-y-2 p-3"><Skeleton className="h-10" /><Skeleton className="h-10" /></div> : null}
        {alerts.data && alerts.data.items.length === 0 ? <p className="px-3 py-6 text-center text-xs text-fg-subtle">No unread alerts.</p> : null}
        {alerts.data && alerts.data.items.length > 0 ? (
          <ul className="max-h-96 divide-y divide-border overflow-y-auto">{alerts.data.items.map((a) => <AlertRow key={a.id} a={a} compact onAck={(id) => ack.mutate(id)} />)}</ul>
        ) : null}
        <div className="border-t border-border px-3 py-2 text-right">
          <Link href="/monitoring" className="text-xs text-accent-bright hover:underline">Open Monitoring</Link>
        </div>
      </PopoverContent>
    </Popover>
  );
}
