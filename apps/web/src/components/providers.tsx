"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useUiStore } from "@/lib/store";
import { Toaster } from "@/components/ui/toast";

function DensitySync() {
  const density = useUiStore((s) => s.density);
  useEffect(() => {
    document.documentElement.dataset.density = density;
  }, [density]);
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5_000,
            refetchOnWindowFocus: false,
            // Auth and not-found errors are final; retrying only delays the UI.
            retry: (count, err) =>
              !(err instanceof ApiError && [401, 403, 404, 422].includes(err.status)) && count < 2,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider delayDuration={200}>
        <DensitySync />
        {children}
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
