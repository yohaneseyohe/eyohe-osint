"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiPatch, errorMessage } from "@/lib/api";
import { qk, useSettings } from "@/lib/queries";
import type { SettingsView } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/toast";
import { Mono } from "@/components/shared/mono";
import { ErrorState, LoadingState } from "@/components/shared/states";

export function effectiveValue(s: SettingsView, key: string): unknown {
  return key in s.overrides ? s.overrides[key] : s.env[key];
}

/** Editable runtime settings for the given keys; everything else is read-only from .env. */
export function SettingsForm({ keys, title, description, isAdmin }: { keys: string[]; title: string; description?: string; isAdmin: boolean }) {
  const qc = useQueryClient();
  const settings = useSettings();
  const [draft, setDraft] = useState<Record<string, string>>({});
  const save = useMutation({
    mutationFn: (payload: Record<string, string | number>) => apiPatch<{ applied: Record<string, unknown> }>("/settings", payload),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: qk.settings }); setDraft({}); toast.success("Settings saved", Object.keys(r.applied).join(", ")); },
    onError: (e) => toast.error("Could not save settings", errorMessage(e)),
  });
  if (settings.isPending) return <LoadingState rows={4} />;
  if (settings.isError) return <ErrorState error={settings.error} onRetry={() => settings.refetch()} />;
  const s = settings.data;
  const editable = keys.filter((k) => s.editable.includes(k));
  const dirty = Object.keys(draft).length > 0;
  const submit = () => {
    const payload: Record<string, string | number> = {};
    for (const [k, v] of Object.entries(draft)) {
      const current = effectiveValue(s, k);
      payload[k] = typeof current === "number" ? Number(v) : v;
    }
    save.mutate(payload);
  };
  return (
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <div>
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
        {description ? <p className="text-xs text-fg-muted">{description}</p> : null}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {keys.map((k) => {
          const value = effectiveValue(s, k);
          const isEditable = editable.includes(k) && isAdmin;
          const overridden = k in s.overrides;
          return (
            <div key={k} className="space-y-1">
              <Label htmlFor={`st-${k}`} className="flex items-center gap-2">
                <Mono className="normal-case">{k}</Mono>
                {overridden ? <span className="text-[9px] text-accent-bright">runtime override</span> : null}
                {!editable.includes(k) ? <span className="text-[9px] text-fg-subtle">.env only</span> : null}
              </Label>
              <Input id={`st-${k}`} value={draft[k] ?? (value === undefined || value === null ? "" : String(value))} onChange={(e) => setDraft({ ...draft, [k]: e.target.value })} disabled={!isEditable} className="font-mono text-xs" />
            </div>
          );
        })}
      </div>
      {isAdmin && editable.length > 0 ? (
        <div className="flex gap-2">
          <Button type="submit" size="sm" loading={save.isPending} disabled={!dirty}>Save changes</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setDraft({})} disabled={!dirty}>Discard</Button>
        </div>
      ) : !isAdmin ? <p className="text-xs text-fg-subtle">Only administrators can change runtime settings.</p> : null}
    </form>
  );
}

export function ReadOnlySettings({ keys, title, description }: { keys: string[]; title: string; description?: string }) {
  const settings = useSettings();
  if (settings.isPending) return <LoadingState rows={4} />;
  if (settings.isError) return <ErrorState error={settings.error} onRetry={() => settings.refetch()} />;
  const s = settings.data;
  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
        {description ? <p className="text-xs text-fg-muted">{description}</p> : null}
      </div>
      <dl className="divide-y divide-border rounded-md border border-border">
        {keys.filter((k) => k in s.env).map((k) => {
          const v = effectiveValue(s, k);
          return (
            <div key={k} className="grid grid-cols-[14rem_1fr] gap-3 px-3 py-2 text-xs">
              <dt><Mono className="text-fg-muted">{k}</Mono></dt>
              <dd className="break-all"><Mono className="text-fg">{v === "" || v === null || v === undefined ? <span className="text-fg-subtle">not set</span> : String(v)}</Mono></dd>
            </div>
          );
        })}
      </dl>
      <p className="text-[11px] text-fg-subtle">{s.note}</p>
    </div>
  );
}
