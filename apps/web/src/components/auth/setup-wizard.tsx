"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, RefreshCw } from "lucide-react";
import { apiPost, errorMessage } from "@/lib/api";
import { qk, useHealth, useSetupStatus } from "@/lib/queries";
import type { HealthComponent, SessionOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { HealthChip } from "@/components/shared/badges";
import { ErrorState } from "@/components/shared/states";
import { SkeletonRows } from "@/components/ui/skeleton";
import { AuthShell } from "./auth-shell";
import { cn } from "@/lib/utils";

const STEPS = ["System check", "Admin account", "Ready"];

function HealthList({ components }: { components: HealthComponent[] }) {
  return (
    <ul className="divide-y divide-border rounded-md border border-border">
      {components.map((c) => {
        const models = Array.isArray(c.detail.models) ? (c.detail.models as string[]) : null;
        return (
          <li key={c.name} className="flex items-start justify-between gap-3 px-3 py-2">
            <div className="min-w-0">
              <p className="text-sm text-fg capitalize">{c.name}</p>
              {c.message ? <p className="truncate text-xs text-fg-muted">{c.message}</p> : null}
              {models && models.length > 0 ? (
                <p className="mt-0.5 font-mono text-[11px] text-fg-subtle">models: {models.join(", ")}</p>
              ) : null}
            </div>
            <HealthChip value={c.status} />
          </li>
        );
      })}
    </ul>
  );
}

export function SetupWizard() {
  const router = useRouter();
  const qc = useQueryClient();
  const setup = useSetupStatus();
  const health = useHealth(false);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({ email: "", username: "", display_name: "", password: "", confirm: "" });

  useEffect(() => {
    if (setup.data && !setup.data.needs_setup && step !== 2) router.replace("/login");
  }, [setup.data, router, step]);

  const create = useMutation({
    mutationFn: () =>
      apiPost<SessionOut>(
        "/auth/setup",
        { email: form.email, username: form.username, password: form.password, display_name: form.display_name },
        { noRedirect: true },
      ),
    onSuccess: (session) => {
      qc.setQueryData(qk.session, session);
      qc.invalidateQueries({ queryKey: qk.setup });
      setStep(2);
      health.refetch();
    },
  });

  const mismatch = form.confirm.length > 0 && form.password !== form.confirm;

  return (
    <AuthShell title="Welcome to Eyohe OSINT" subtitle="First-run setup creates the administrator account for this workstation.">
      <ol className="mb-5 flex items-center gap-2 text-xs">
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-2">
            <span
              className={cn(
                "flex size-5 items-center justify-center rounded-full border font-mono text-[10px]",
                i === step ? "border-accent bg-accent text-white" : i < step ? "border-success text-success" : "border-border text-fg-subtle",
              )}
            >
              {i + 1}
            </span>
            <span className={i === step ? "text-fg" : "text-fg-subtle"}>{s}</span>
            {i < STEPS.length - 1 ? <span className="mx-1 h-px w-6 bg-border" /> : null}
          </li>
        ))}
      </ol>

      {step === 0 ? (
        <div className="space-y-4">
          {health.isPending ? <SkeletonRows rows={5} /> : null}
          {health.isError ? <ErrorState error={health.error} onRetry={() => health.refetch()} /> : null}
          {health.data ? <HealthList components={health.data.components} /> : null}
          <div className="flex justify-between">
            <Button variant="ghost" size="sm" onClick={() => health.refetch()} loading={health.isFetching}>
              <RefreshCw /> Re-check
            </Button>
            <Button onClick={() => setStep(1)}>
              Continue <ArrowRight />
            </Button>
          </div>
        </div>
      ) : null}

      {step === 1 ? (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (!mismatch) create.mutate();
          }}
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="su-email">Email</Label>
              <Input id="su-email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="su-username">Username</Label>
              <Input id="su-username" required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="su-display">Display name</Label>
              <Input id="su-display" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="su-password">Password</Label>
              <Input id="su-password" type="password" required minLength={12} autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="su-confirm">Confirm</Label>
              <Input id="su-confirm" type="password" required autoComplete="new-password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} aria-invalid={mismatch} />
            </div>
          </div>
          {mismatch ? <p className="text-xs text-danger">Passwords do not match.</p> : null}
          {create.isError ? (
            <p role="alert" className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
              {errorMessage(create.error)}
            </p>
          ) : null}
          <div className="flex justify-between">
            <Button type="button" variant="ghost" onClick={() => setStep(0)}>
              Back
            </Button>
            <Button type="submit" loading={create.isPending} disabled={mismatch}>
              Create admin account
            </Button>
          </div>
        </form>
      ) : null}

      {step === 2 ? (
        <div className="space-y-4">
          <p className="text-sm text-fg">Administrator created and signed in. Final health check:</p>
          {health.data ? <HealthList components={health.data.components} /> : <SkeletonRows rows={5} />}
          <div className="flex justify-between">
            <Button variant="ghost" size="sm" onClick={() => health.refetch()} loading={health.isFetching}>
              <RefreshCw /> Re-check
            </Button>
            <Button asChild>
              <Link href="/">
                Open Command Center <ArrowRight />
              </Link>
            </Button>
          </div>
        </div>
      ) : null}
    </AuthShell>
  );
}
