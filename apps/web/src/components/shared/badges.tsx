import { Badge } from "@/components/ui/badge";
import { SimpleTooltip } from "@/components/ui/tooltip";
import {
  CASE_STATUS_STYLE,
  CONFIDENCE_STYLE,
  HEALTH_STYLE,
  INVESTIGATION_STATUS_STYLE,
  REVIEW_STYLE,
  STAGE_STYLE,
  TIER_LABELS,
  TIER_STYLE,
} from "@/lib/labels";
import type { Confidence, ReviewState } from "@/lib/types";
import { cn, humanize } from "@/lib/utils";

const base = "inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium leading-none whitespace-nowrap";

export function ConfidenceBadge({ value, className }: { value: string; className?: string }) {
  const style = CONFIDENCE_STYLE[value as Confidence];
  return (
    <span className={cn(base, style?.className ?? "border-border text-fg-muted", className)} title={`Confidence: ${value}`}>
      {value}
    </span>
  );
}

export function ReviewChip({ value, className }: { value: string; className?: string }) {
  const style = REVIEW_STYLE[value as ReviewState];
  return <span className={cn(base, style ?? "border-border text-fg-muted", className)}>{humanize(value)}</span>;
}

export function TierBadge({ tier, verbose = false, className }: { tier: number; verbose?: boolean; className?: string }) {
  const label = TIER_LABELS[tier] ?? "unknown tier";
  const chip = (
    <span className={cn(base, TIER_STYLE[tier] ?? "border-border text-fg-muted", className)}>
      Tier {tier}
      {verbose ? <span className="ml-1 font-normal opacity-90">{label}</span> : null}
    </span>
  );
  return verbose ? chip : <SimpleTooltip content={`Tier ${tier}: ${label}`}>{chip}</SimpleTooltip>;
}

export function InvestigationStatusChip({ value, className }: { value: string; className?: string }) {
  const live = value === "RUNNING" || value === "VERIFYING" || value === "PLANNING";
  return (
    <span className={cn(base, "gap-1.5", INVESTIGATION_STATUS_STYLE[value] ?? "border-border text-fg-muted", className)}>
      {live ? <span className="size-1.5 rounded-full bg-current animate-pulse" aria-hidden /> : null}
      {humanize(value)}
    </span>
  );
}

export function CaseStatusChip({ value, className }: { value: string; className?: string }) {
  return <span className={cn(base, CASE_STATUS_STYLE[value] ?? "border-border text-fg-muted", className)}>{humanize(value)}</span>;
}

export function TypeChip({ value, className }: { value: string; className?: string }) {
  return (
    <span className={cn(base, "border-border-strong bg-panel-2 text-fg-muted font-mono text-[10px] uppercase", className)}>
      {value}
    </span>
  );
}

export function StageChip({ value, className }: { value: string; className?: string }) {
  const key = (value || "SYSTEM").toUpperCase();
  return (
    <span className={cn(base, "w-16 justify-center font-mono text-[10px] bg-transparent", STAGE_STYLE[key] ?? "text-fg-muted border-border", className)}>
      {key}
    </span>
  );
}

export function HealthChip({ value, className }: { value: string; className?: string }) {
  const style = HEALTH_STYLE[value] ?? HEALTH_STYLE.NOT_CONFIGURED;
  return (
    <span className={cn(base, "gap-1.5", style.chip, className)}>
      <span className={cn("size-1.5 rounded-full", style.dot)} aria-hidden />
      {humanize(value)}
    </span>
  );
}

export function DemoBadge({ show, className }: { show?: boolean; className?: string }) {
  if (!show) return null;
  return (
    <Badge variant="demo" className={className} title="This record was created by the demo seed, not by a real collection">
      DEMO DATA
    </Badge>
  );
}
