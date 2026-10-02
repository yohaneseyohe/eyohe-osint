import { format, formatDistanceToNowStrict, isValid, parseISO } from "date-fns";

function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  const d = typeof value === "string" ? parseISO(value) : value;
  return isValid(d) ? d : null;
}

/** Full technical timestamp, always rendered in monospace by callers. */
export function formatTs(value: string | Date | null | undefined): string {
  const d = toDate(value);
  return d ? format(d, "yyyy-MM-dd HH:mm:ss") : "—";
}

export function formatTime(value: string | Date | null | undefined): string {
  const d = toDate(value);
  return d ? format(d, "HH:mm:ss") : "—";
}

export function formatDate(value: string | Date | null | undefined): string {
  const d = toDate(value);
  return d ? format(d, "yyyy-MM-dd") : "—";
}

export function formatRelative(value: string | Date | null | undefined): string {
  const d = toDate(value);
  return d ? `${formatDistanceToNowStrict(d)} ago` : "—";
}

/** Timeline events carry a precision hint (day/month/year/...) that controls how much we show. */
export function formatWithPrecision(value: string, precision: string): string {
  const d = toDate(value);
  if (!d) return value;
  switch (precision.toLowerCase()) {
    case "year":
      return format(d, "yyyy");
    case "month":
      return format(d, "yyyy-MM");
    case "day":
    case "date":
      return format(d, "yyyy-MM-dd");
    default:
      return format(d, "yyyy-MM-dd HH:mm");
  }
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatNumber(n: number | undefined | null): string {
  return new Intl.NumberFormat("en-US").format(n ?? 0);
}
