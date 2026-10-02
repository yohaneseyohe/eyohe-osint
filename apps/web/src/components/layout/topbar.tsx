"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut, Plus, Search, User } from "lucide-react";
import { apiPost } from "@/lib/api";
import { useSession } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { CommandPalette } from "./command-palette";
import { HealthIndicators } from "./health-indicators";
import { NewInvestigationDialog } from "./new-investigation-dialog";
import { NotificationsBell } from "./notifications";

export function TopBar() {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [newOpen, setNewOpen] = useState(false);
  const session = useSession();
  const router = useRouter();
  const qc = useQueryClient();
  const logout = useMutation({
    mutationFn: () => apiPost("/auth/logout"),
    onSettled: () => {
      qc.clear();
      router.replace("/login");
    },
  });

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-bg/80 px-4 backdrop-blur">
      <button
        onClick={() => setPaletteOpen(true)}
        className="flex h-9 w-full max-w-xl items-center gap-2 rounded-md border border-border bg-bg-elevated px-3 text-left text-sm text-fg-subtle transition-colors hover:border-border-strong hover:text-fg-muted"
        aria-label="Open command palette"
      >
        <Search className="size-4" />
        <span className="flex-1 truncate">Ask Eyohe anything…</span>
        <kbd className="hidden rounded border border-border px-1.5 font-mono text-[10px] text-fg-subtle md:inline">⌘K</kbd>
      </button>
      <div className="ml-auto flex items-center gap-2">
        <Button size="sm" onClick={() => setNewOpen(true)}>
          <Plus /> New Investigation
        </Button>
        <HealthIndicators />
        <NotificationsBell />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label="Account menu">
              <User />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>
              <div className="text-fg">{session.data?.user.display_name || session.data?.user.username}</div>
              <div className="font-mono text-[10px] font-normal text-fg-subtle">{session.data?.user.email}</div>
              <div className="mt-1 text-[10px] font-normal uppercase tracking-wider text-accent-bright">{session.data?.user.role}</div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => router.push("/settings?tab=security")}>Security settings</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => logout.mutate()}>
              <LogOut /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
      <NewInvestigationDialog open={newOpen} onOpenChange={setNewOpen} />
    </header>
  );
}
