"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiPost, errorMessage } from "@/lib/api";
import { qk, useSetupStatus } from "@/lib/queries";
import type { SessionOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "./auth-shell";

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const setup = useSetupStatus();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (setup.data?.needs_setup) router.replace("/setup");
  }, [setup.data, router]);

  const login = useMutation({
    mutationFn: () => apiPost<SessionOut>("/auth/login", { identifier, password }, { noRedirect: true }),
    onSuccess: (session) => {
      qc.setQueryData(qk.session, session);
      const next = params.get("next");
      router.replace(next && next.startsWith("/") ? next : "/");
    },
  });

  return (
    <AuthShell title="Sign in" subtitle="Local analyst workstation. Sessions expire automatically.">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="identifier">Email or username</Label>
          <Input id="identifier" autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} required autoFocus />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {login.isError ? (
          <p role="alert" className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
            {errorMessage(login.error)}
          </p>
        ) : null}
        <Button type="submit" className="w-full" loading={login.isPending}>
          Sign in
        </Button>
      </form>
    </AuthShell>
  );
}
