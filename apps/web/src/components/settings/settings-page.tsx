"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useHealth, useSession } from "@/lib/queries";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { HealthChip } from "@/components/shared/badges";
import { PageHeader } from "@/components/shared/page-header";
import { AiModelsTab } from "./ai-models-tab";
import { AppearanceTab } from "./appearance-tab";
import { AuditLog } from "./audit-log";
import { CollectorsTab } from "./collectors-tab";
import { HealthGrid } from "./health-grid";
import { SecurityTab } from "./security-tab";
import { ReadOnlySettings, SettingsForm } from "./settings-form";

const TABS = ["general", "ai", "search", "collectors", "storage", "security", "appearance", "health", "audit"] as const;
type Tab = (typeof TABS)[number];

function SearchProvidersTab({ isAdmin }: { isAdmin: boolean }) {
  const health = useHealth(30_000);
  const comp = health.data?.components.find((c) => c.name === "search");
  const problems = Array.isArray(comp?.detail.problems) ? (comp.detail.problems as string[]) : [];
  return (
    <div className="space-y-6">
      <div className="rounded-md border border-border bg-panel px-4 py-3 text-xs">
        <div className="flex items-center gap-2">{comp ? <HealthChip value={comp.status} /> : null}<span className="text-fg-muted">{comp?.message ?? "Checking…"}</span></div>
        {problems.map((p, i) => <p key={i} className="mt-1 text-warning">{p}</p>)}
        <p className="mt-2 text-fg-subtle">Provider API keys (Brave, Serper, Tavily) are configured in <code className="font-mono">.env</code> and shown masked below.</p>
      </div>
      <SettingsForm isAdmin={isAdmin} title="Active providers" description="Comma-separated provider list used by search tasks." keys={["search_providers", "searxng_url"]} />
      <ReadOnlySettings title="Provider credentials" keys={["brave_api_key", "serper_api_key", "tavily_api_key", "github_token"]} />
    </div>
  );
}

export function SettingsPage({ initialTab }: { initialTab?: Tab }) {
  const router = useRouter();
  const params = useSearchParams();
  const session = useSession();
  const isAdmin = session.data?.user.role === "admin";
  const tabParam = initialTab ?? params.get("tab");
  const tab: Tab = TABS.includes(tabParam as Tab) ? (tabParam as Tab) : "general";

  return (
    <div>
      <PageHeader title="Settings" subtitle="Runtime configuration, local AI models, collectors, security and system health." actions={<Link href="/settings/audit" className="text-xs text-accent-bright hover:underline">Open full audit log</Link>} />
      <Tabs value={tab} onValueChange={(v) => router.replace(v === "audit" ? "/settings/audit" : `/settings?tab=${v}`, { scroll: false })}>
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="ai">AI Models</TabsTrigger>
          <TabsTrigger value="search">Search Providers</TabsTrigger>
          <TabsTrigger value="collectors">Collectors</TabsTrigger>
          <TabsTrigger value="storage">Database / Graph / Storage</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="appearance">Appearance</TabsTrigger>
          <TabsTrigger value="health">System Health</TabsTrigger>
          <TabsTrigger value="audit">Audit</TabsTrigger>
        </TabsList>
        <TabsContent value="general" className="space-y-6">
          <SettingsForm isAdmin={isAdmin} title="Workstation" description="Classification stamped on reports and retention of raw evidence." keys={["report_classification", "evidence_retention_days"]} />
          <ReadOnlySettings title="Environment" keys={["eyohe_env", "public_base_url", "cors_origins", "log_level", "session_ttl_hours", "rate_limit_per_minute", "user_agent"]} />
        </TabsContent>
        <TabsContent value="ai"><AiModelsTab isAdmin={isAdmin} /></TabsContent>
        <TabsContent value="search"><SearchProvidersTab isAdmin={isAdmin} /></TabsContent>
        <TabsContent value="collectors"><CollectorsTab /></TabsContent>
        <TabsContent value="storage" className="space-y-6">
          <ReadOnlySettings title="Database" keys={["database_url", "redis_url", "job_backend"]} />
          <SettingsForm isAdmin={isAdmin} title="Graph backend" keys={["graph_backend"]} />
          <ReadOnlySettings title="Evidence storage" keys={["data_dir", "snapshot_max_text_chars", "max_fetch_bytes", "request_timeout", "allow_private_network_fetch", "chromium_path"]} />
        </TabsContent>
        <TabsContent value="security"><SecurityTab isAdmin={isAdmin} /></TabsContent>
        <TabsContent value="appearance"><AppearanceTab /></TabsContent>
        <TabsContent value="health"><HealthGrid /></TabsContent>
        <TabsContent value="audit"><AuditLog /></TabsContent>
      </Tabs>
    </div>
  );
}
