"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bell,
  Briefcase,
  ChevronsLeft,
  ChevronsRight,
  Clock,
  FileText,
  Globe,
  LayoutDashboard,
  Network,
  Search,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useUiStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { SimpleTooltip } from "@/components/ui/tooltip";
import { Brand } from "./brand";

const NAV = [
  { href: "/", label: "Command Center", icon: LayoutDashboard },
  { href: "/investigations", label: "Investigations", icon: Activity },
  { href: "/cases", label: "Cases", icon: Briefcase },
  { href: "/evidence", label: "Evidence", icon: ShieldCheck },
  { href: "/entities", label: "Entities", icon: Users },
  { href: "/graph", label: "Graph", icon: Network },
  { href: "/timeline", label: "Timeline", icon: Clock },
  { href: "/sources", label: "Sources", icon: Globe },
  { href: "/search", label: "Search", icon: Search },
  { href: "/monitoring", label: "Monitoring", icon: Bell },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);

  return (
    <aside
      className={cn(
        "sticky top-0 flex h-screen shrink-0 flex-col border-r border-border bg-panel/70 transition-[width] duration-200",
        collapsed ? "w-16" : "w-60",
      )}
      aria-label="Primary"
    >
      <div className={cn("flex h-14 items-center border-b border-border", collapsed ? "justify-center px-2" : "px-4")}>
        <Link href="/" className="min-w-0" aria-label="EYOHE OSINT home">
          <Brand collapsed={collapsed} />
        </Link>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="space-y-0.5">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            const link = (
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group flex h-9 items-center gap-3 rounded-md px-2.5 text-sm transition-colors",
                  active ? "bg-accent-soft text-accent-bright" : "text-fg-muted hover:bg-panel-2 hover:text-fg",
                  collapsed && "justify-center px-0",
                )}
              >
                <Icon className={cn("size-4 shrink-0", active ? "text-accent-bright" : "text-fg-subtle group-hover:text-fg")} />
                {!collapsed ? <span className="truncate">{label}</span> : <span className="sr-only">{label}</span>}
              </Link>
            );
            return <li key={href}>{collapsed ? <SimpleTooltip content={label}>{link}</SimpleTooltip> : link}</li>;
          })}
        </ul>
      </nav>
      <div className="border-t border-border p-2">
        <button
          onClick={toggle}
          className={cn(
            "flex h-8 w-full items-center gap-2 rounded-md px-2.5 text-xs text-fg-subtle hover:bg-panel-2 hover:text-fg",
            collapsed && "justify-center px-0",
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
          {!collapsed ? <span>Collapse</span> : null}
        </button>
      </div>
    </aside>
  );
}
