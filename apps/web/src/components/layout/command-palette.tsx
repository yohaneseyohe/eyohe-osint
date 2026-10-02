"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, Briefcase, Clock, FileText, Globe, LayoutDashboard, Network, Search, Settings, ShieldCheck, Users } from "lucide-react";
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Mono } from "@/components/shared/mono";
import { useCases } from "@/lib/queries";

const PAGES = [
  { href: "/", label: "Command Center", icon: LayoutDashboard },
  { href: "/investigations", label: "Investigations", icon: Activity },
  { href: "/cases", label: "Cases", icon: Briefcase },
  { href: "/evidence", label: "Evidence", icon: ShieldCheck },
  { href: "/entities", label: "Entities", icon: Users },
  { href: "/graph", label: "Graph", icon: Network },
  { href: "/timeline", label: "Timeline", icon: Clock },
  { href: "/sources", label: "Sources", icon: Globe },
  { href: "/search", label: "Search", icon: Search },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const cases = useCases({ page_size: 50 });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  const go = (href: string) => {
    onOpenChange(false);
    setQuery("");
    router.push(href);
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput
        value={query}
        onValueChange={setQuery}
        placeholder="Ask Eyohe anything… (Enter to search)"
        onKeyDown={(e) => {
          // Free text submits to the Query Playground when nothing in the list matched.
          if (e.key === "Enter" && query.trim() && !document.querySelector('[cmdk-item][data-selected="true"]')) {
            e.preventDefault();
            go(`/search?q=${encodeURIComponent(query.trim())}`);
          }
        }}
      />
      <CommandList>
        <CommandEmpty>
          No match. Press Enter to search for <span className="text-fg">“{query}”</span>.
        </CommandEmpty>
        {query.trim() ? (
          <CommandGroup heading="Search">
            <CommandItem value={`search ${query}`} onSelect={() => go(`/search?q=${encodeURIComponent(query.trim())}`)}>
              <Search /> Search for “{query.trim()}”
            </CommandItem>
          </CommandGroup>
        ) : null}
        {cases.data && cases.data.items.length > 0 ? (
          <CommandGroup heading="Cases">
            {cases.data.items.map((c) => (
              <CommandItem key={c.id} value={`${c.display_id} ${c.name}`} onSelect={() => go(`/cases/${c.id}`)}>
                <Briefcase />
                <Mono className="text-fg-subtle">{c.display_id}</Mono>
                <span className="truncate">{c.name}</span>
                {c.is_demo ? <span className="ml-auto text-[10px] text-warning">DEMO</span> : null}
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}
        <CommandGroup heading="Navigate">
          {PAGES.map((p) => (
            <CommandItem key={p.href} value={`go ${p.label}`} onSelect={() => go(p.href)}>
              <p.icon /> {p.label}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
