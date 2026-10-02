"use client";

import { useAiModels, useHealth, useSettings } from "@/lib/queries";
import { HealthChip } from "@/components/shared/badges";
import { Mono } from "@/components/shared/mono";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SettingsForm, effectiveValue } from "./settings-form";

export function AiModelsTab({ isAdmin }: { isAdmin: boolean }) {
  const health = useHealth(30_000);
  const settings = useSettings();
  const ai = useAiModels();
  const ollama = health.data?.components.find((c) => c.name === "ollama");
  const models = ai.data?.models ?? [];
  const configured = ai.data?.configured ?? (settings.data ? String(effectiveValue(settings.data, "ollama_model") ?? "") : "");
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle>Ollama</CardTitle>{ollama ? <HealthChip value={ollama.status} /> : null}</CardHeader>
        <CardContent className="space-y-3 text-xs">
          <p className="text-fg-muted">{ollama?.message ?? (health.isPending ? "Checking…" : "Ollama not reported by /health.")}</p>
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wider text-fg-subtle">Detected models</p>
            {ai.data && !ai.data.available ? <p className="text-warning">Ollama is not reachable; configured model <Mono>{ai.data.configured}</Mono>.</p> : null}
            {ai.isPending ? <p className="text-fg-subtle">Loading models…</p> : null}
            {ai.data?.available && models.length === 0 ? <p className="text-fg-subtle">No models detected. Pull one with <Mono>ollama pull qwen3:8b</Mono>.</p> : null}
            {models.length > 0 ? (
              <ul className="divide-y divide-border rounded-md border border-border">
                {models.map((m) => (
                  <li key={m.name} className={`flex items-center gap-3 px-2.5 py-1.5 ${m.name === configured ? "bg-accent-soft" : ""}`}>
                    <Mono className={m.name === configured ? "text-accent-bright" : "text-fg"}>{m.name}</Mono>
                    {m.name === configured ? <span className="text-[10px] uppercase text-accent-bright">active</span> : null}
                    <span className="ml-auto text-fg-subtle">{m.family ?? "—"} · {m.parameters ?? "—"} · {m.size_gb} GB</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <p className="text-fg-subtle">All AI planning and summarisation runs locally through Ollama. The model only drafts from collected evidence; it cannot add sources.</p>
        </CardContent>
      </Card>
      <SettingsForm isAdmin={isAdmin} title="Model and research bounds" description="Runtime-editable; overrides are stored in the database and survive restarts." keys={["ollama_model", "ollama_url", "ollama_timeout_seconds", "ollama_num_ctx", "max_agent_iterations", "max_research_depth", "max_queries", "max_pages", "max_runtime_seconds", "max_results_per_source"]} />
    </div>
  );
}
