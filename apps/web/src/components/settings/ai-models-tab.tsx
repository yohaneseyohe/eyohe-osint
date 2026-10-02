"use client";

import { useHealth, useSettings } from "@/lib/queries";
import { HealthChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SettingsForm, effectiveValue } from "./settings-form";

export function AiModelsTab({ isAdmin }: { isAdmin: boolean }) {
  const health = useHealth(30_000);
  const settings = useSettings();
  const ollama = health.data?.components.find((c) => c.name === "ollama");
  const models = Array.isArray(ollama?.detail.models) ? (ollama.detail.models as string[]) : [];
  const configured = settings.data ? String(effectiveValue(settings.data, "ollama_model") ?? "") : "";
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle>Ollama</CardTitle>{ollama ? <HealthChip value={ollama.status} /> : null}</CardHeader>
        <CardContent className="space-y-3 text-xs">
          <p className="text-fg-muted">{ollama?.message ?? (health.isPending ? "Checking…" : "Ollama not reported by /health.")}</p>
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wider text-fg-subtle">Detected models</p>
            {models.length === 0 ? <p className="text-fg-subtle">No models detected. Pull one with <Mono>ollama pull qwen3:8b</Mono>.</p> : (
              <ul className="flex flex-wrap gap-1.5">
                {models.map((m) => (
                  <li key={m} className={`rounded border px-2 py-1 font-mono ${m === configured ? "border-accent bg-accent-soft text-accent-bright" : "border-border bg-bg-elevated text-fg-muted"}`}>
                    {m}{m === configured ? " · active" : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <p className="text-fg-subtle">All AI planning and summarisation runs locally through Ollama. The model only drafts from collected evidence; it cannot add sources.</p>
        </CardContent>
      </Card>
      <SettingsForm isAdmin={isAdmin} title="Model and research bounds" description="Runtime-editable; overrides are stored in the database and survive restarts." keys={["ollama_model", "ollama_url", "ollama_timeout_seconds", "ollama_num_ctx", "max_agent_iterations", "max_research_depth", "max_queries", "max_pages", "max_runtime_seconds", "max_results_per_source"]} />
    </div>
  );
}
