import { Radar } from "lucide-react";
import { cn } from "@/lib/utils";

export function Brand({ collapsed = false, size = "md" }: { collapsed?: boolean; size?: "md" | "lg" }) {
  return (
    <div className={cn("flex items-center gap-2.5", collapsed && "justify-center")}>
      <div className="flex size-8 shrink-0 items-center justify-center rounded-md border border-accent/40 bg-accent-soft text-accent-bright">
        <Radar className="size-4" />
      </div>
      {!collapsed ? (
        <div className="min-w-0 leading-tight">
          <div className={cn("font-semibold tracking-[0.18em] text-fg", size === "lg" ? "text-base" : "text-xs")}>EYOHE OSINT</div>
          <div className={cn("truncate text-fg-subtle", size === "lg" ? "text-xs" : "text-[10px]")}>
            Public Intelligence. Connected Evidence.
          </div>
        </div>
      ) : null}
    </div>
  );
}
