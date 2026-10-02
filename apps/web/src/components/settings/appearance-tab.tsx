"use client";

import { useUiStore, type Density } from "@/lib/store";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function AppearanceTab() {
  const density = useUiStore((s) => s.density);
  const setDensity = useUiStore((s) => s.setDensity);
  const options: { value: Density; label: string; hint: string }[] = [
    { value: "comfortable", label: "Comfortable", hint: "Default spacing and 16px base text." },
    { value: "compact", label: "Compact", hint: "Tighter 14px base for large monitors and dense tables." },
  ];
  return (
    <Card>
      <CardHeader><CardTitle>Density</CardTitle></CardHeader>
      <CardContent>
        <div className="grid max-w-xl gap-2 md:grid-cols-2" role="radiogroup" aria-label="Interface density">
          {options.map((o) => (
            <button key={o.value} role="radio" aria-checked={density === o.value} onClick={() => setDensity(o.value)} className={cn("rounded-md border px-3 py-2.5 text-left transition-colors", density === o.value ? "border-accent bg-accent-soft" : "border-border hover:border-border-strong")}>
              <div className="text-sm text-fg">{o.label}</div>
              <div className="text-xs text-fg-muted">{o.hint}</div>
            </button>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-fg-subtle">Stored in this browser only. The workstation is dark-only by design.</p>
      </CardContent>
    </Card>
  );
}
