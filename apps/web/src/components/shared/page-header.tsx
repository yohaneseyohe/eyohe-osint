import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  subtitle,
  actions,
  className,
  children,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={cn("mb-5 flex flex-col gap-3", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-tight text-fg flex items-center gap-2 flex-wrap">{title}</h1>
          {subtitle ? <div className="mt-0.5 text-xs text-fg-muted">{subtitle}</div> : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </div>
  );
}

export function SectionTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h2 className={cn("text-[11px] font-semibold uppercase tracking-wider text-fg-muted", className)}>{children}</h2>;
}

export function KeyValue({ label, children, mono = false }: { label: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] uppercase tracking-wider text-fg-subtle">{label}</dt>
      <dd className={cn("mt-0.5 text-sm text-fg break-words", mono && "font-mono text-xs")}>{children}</dd>
    </div>
  );
}
