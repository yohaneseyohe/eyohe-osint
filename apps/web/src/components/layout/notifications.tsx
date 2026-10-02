"use client";

import Link from "next/link";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useDashboard } from "@/lib/queries";

export function NotificationsBell() {
  const dash = useDashboard();
  const unread = dash.data?.unread_alerts ?? 0;
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
      <PopoverContent className="w-72">
        <p className="text-xs font-semibold uppercase tracking-wider text-fg-muted">Alerts</p>
        <p className="mt-2 text-sm text-fg">
          {unread === 0 ? "No unread alerts." : `${unread} unread alert${unread === 1 ? "" : "s"}.`}
        </p>
        <p className="mt-1 text-xs text-fg-subtle">
          Alert details and monitoring rules arrive with the Monitoring phase.{" "}
          <Link href="/monitoring" className="text-accent-bright hover:underline">
            Open Monitoring
          </Link>
        </p>
      </PopoverContent>
    </Popover>
  );
}
