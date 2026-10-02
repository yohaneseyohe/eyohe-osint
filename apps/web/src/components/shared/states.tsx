import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SkeletonRows } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = Inbox,
  className,
}: {
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-lg border border-dashed border-border px-6 py-12 text-center", className)}>
      <div className="mb-3 flex size-10 items-center justify-center rounded-full bg-panel-2 text-fg-subtle">
        <Icon className="size-5" />
      </div>
      <p className="text-sm font-medium text-fg">{title}</p>
      {description ? <p className="mt-1 max-w-md text-xs text-fg-muted">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  compact = false,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  compact?: boolean;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-lg border border-danger/30 bg-danger/5 text-sm",
        compact ? "px-3 py-2" : "px-4 py-3",
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-danger">Request failed</p>
        <p className="mt-0.5 break-words text-xs text-fg-muted">{errorMessage(error)}</p>
      </div>
      {onRetry ? (
        <Button variant="outline" size="xs" onClick={onRetry}>
          <RefreshCw /> Retry
        </Button>
      ) : null}
    </div>
  );
}

export function LoadingState({ rows = 6, className }: { rows?: number; className?: string }) {
  return <SkeletonRows rows={rows} className={className} />;
}

/** Standard loading/error/empty switch for list views; children render when there is data. */
export function QueryState<T>({
  query,
  empty,
  rows,
  isEmpty,
  children,
}: {
  query: { data: T | undefined; isPending: boolean; isError: boolean; error: unknown; refetch: () => void };
  empty: React.ReactNode;
  rows?: number;
  isEmpty: (data: T) => boolean;
  children: (data: T) => React.ReactNode;
}) {
  if (query.isPending) return <LoadingState rows={rows} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  if (query.data === undefined || isEmpty(query.data)) return <>{empty}</>;
  return <>{children(query.data)}</>;
}
