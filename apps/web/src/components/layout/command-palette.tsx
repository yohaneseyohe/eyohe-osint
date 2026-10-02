"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, Briefcase, Clock, FileText, Globe, LayoutDashboard, Network, Search, Settings, ShieldCheck, Users } from "lucide-react";
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Mono } from "@/components/shared/mono";
import { useMutation } from "@tanstack/react-query";
import { apiPost, errorMessage } from "@/lib/api";
import { useCases } from "@/lib/queries";
import { useUiStore } from "@/lib/store";
import type { AIQueryResponse } from "@/lib/types";
import { toast } from "@/components/ui/toast";

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
  const selectedCase = useUiStore((s) => s.selectedCaseId);
  const askEyohe = useMutation({
    mutationFn: (question: string) => apiPost<AIQueryResponse>("/ai/query", { case_id: selectedCase, question, mode: "route" }),
    onSuccess: (r, question) => {
      // Intent routes are case-relative; without a case the backend returns a bare "?tab=…" we cannot use.
      const route = r.intent.route;
      if (route.startsWith("/")) go(route);
      else if (r.intent.kind === "ask") { toast.info("Select a case to ask the analyst", "Pick a case on any case page, then ask again."); go(`/search?q=${encodeURIComponent(question)}`); }
      else go(`/search?q=${encodeURIComponent(question)}`);
    },
    onError: (e, question) => { toast.error("Could not interpret the request", errorMessage(e)); go(`/search?q=${encodeURIComponent(question)}`); },
  });
  const submitFreeText = (text: string) => askEyohe.mutate(text.trim());

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
        placeholder="Ask Eyohe anything… (Enter to ask)"
        onKeyDown={(e) => {
          // Free text submits to the Query Playground when nothing in the list matched.
          if (e.key === "Enter" && query.trim() && !document.querySelector('[cmdk-item][data-selected="true"]')) {
            e.preventDefault();
            submitFreeText(query);
          }
        }}
      />
      <CommandList>
        <CommandEmpty>
          No match. Press Enter to search for <span className="text-fg">“{query}”</span>.
        </CommandEmpty>
        {query.trim() ? (
          <CommandGroup heading="Search">
            <CommandItem value={`ask ${query}`} onSelect={() => submitFreeText(query)}>
              <Search /> Ask Eyohe: “{query.trim()}”{selectedCase ? "" : " (no case selected)"}
            </CommandItem>
            <CommandItem value={`search ${query}`} onSelect={() => go(`/search?q=${encodeURIComponent(query.trim())}`)}>
              <Search /> Run as web search
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
