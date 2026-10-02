"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { ApiError } from "@/lib/api";
import { useSession, useSetupStatus } from "@/lib/queries";
import { Skeleton } from "@/components/ui/skeleton";

/** Client-side session gate: 401 → /login (or /setup on a fresh install). */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const session = useSession();
  const unauthenticated = session.isError && session.error instanceof ApiError && session.error.status === 401;
  const setup = useSetupStatus();

  useEffect(() => {
    if (!unauthenticated) return;
    if (setup.data?.needs_setup) router.replace("/setup");
    else if (setup.data) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      router.replace(`/login?next=${next}`);
    }
  }, [unauthenticated, setup.data, router]);

  if (session.isPending || unauthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <div className="w-72 space-y-3">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
        </div>
      </div>
    );
  }
  if (session.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg px-6 text-center">
        <div>
          <p className="text-sm font-medium text-danger">Cannot reach the Eyohe API</p>
          <p className="mt-1 text-xs text-fg-muted">{session.error.message}</p>
          <button className="mt-4 text-xs text-accent-bright underline" onClick={() => session.refetch()}>
            Retry
          </button>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
