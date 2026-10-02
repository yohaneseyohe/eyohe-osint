import * as React from "react";
import { cn } from "@/lib/utils";

/** Monospace wrapper for IDs, URLs, hashes and timestamps. */
export function Mono({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("font-mono text-[0.85em] tabular-nums tracking-tight", className)} {...props} />;
}
