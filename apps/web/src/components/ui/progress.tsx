import { cn } from "@/lib/utils";

export function Progress({
  value,
  className,
  color = "bg-accent",
  label,
}: {
  value: number;
  className?: string;
  color?: string;
  label?: string;
}) {
  const v = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div
      role="progressbar"
      aria-valuenow={v}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? "Progress"}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-panel-2", className)}
    >
      <div className={cn("h-full rounded-full transition-[width] duration-500 ease-out", color)} style={{ width: `${v}%` }} />
    </div>
  );
}
