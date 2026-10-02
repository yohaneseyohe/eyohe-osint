import type { Confidence, ReviewState } from "./types";

export const CONFIDENCE_ORDER: Confidence[] = [
  "CONFIRMED",
  "CORROBORATED",
  "SUPPORTED",
  "POSSIBLE",
  "INFERENCE",
  "UNVERIFIED",
  "CONTRADICTED",
];

/** Tailwind classes + CSS color per confidence level; one scale used everywhere. */
export const CONFIDENCE_STYLE: Record<Confidence, { className: string; color: string }> = {
  CONFIRMED: { className: "bg-success/15 text-success border-success/30", color: "var(--success)" },
  CORROBORATED: { className: "bg-teal/15 text-teal border-teal/30", color: "var(--teal)" },
  SUPPORTED: { className: "bg-info/15 text-accent-bright border-info/30", color: "var(--info)" },
  POSSIBLE: { className: "bg-slate/15 text-slate border-slate/30", color: "var(--slate)" },
  INFERENCE: { className: "bg-violet/15 text-violet border-violet/30", color: "var(--violet)" },
  UNVERIFIED: { className: "bg-warning/15 text-warning border-warning/30", color: "var(--warning)" },
  CONTRADICTED: { className: "bg-danger/15 text-danger border-danger/30", color: "var(--danger)" },
};

export const REVIEW_ORDER: ReviewState[] = ["PENDING", "ACCEPTED", "REJECTED", "NEEDS_VERIFICATION"];

export const REVIEW_STYLE: Record<ReviewState, string> = {
  PENDING: "bg-slate/10 text-fg-muted border-border-strong",
  ACCEPTED: "bg-success/15 text-success border-success/30",
  REJECTED: "bg-danger/15 text-danger border-danger/30",
  NEEDS_VERIFICATION: "bg-warning/15 text-warning border-warning/30",
};

export const TIER_LABELS: Record<number, string> = {
  1: "official primary source",
  2: "reputable secondary source",
  3: "public technical database",
  4: "community discussion",
  5: "unverified",
};

export const TIER_STYLE: Record<number, string> = {
  1: "bg-success/15 text-success border-success/30",
  2: "bg-teal/15 text-teal border-teal/30",
  3: "bg-info/15 text-accent-bright border-info/30",
  4: "bg-warning/15 text-warning border-warning/30",
  5: "bg-slate/15 text-slate border-slate/30",
};

export const INVESTIGATION_STATUS_STYLE: Record<string, string> = {
  DRAFT: "bg-slate/10 text-fg-muted border-border-strong",
  PLANNING: "bg-violet/15 text-violet border-violet/30",
  AWAITING_APPROVAL: "bg-warning/15 text-warning border-warning/30",
  RUNNING: "bg-info/15 text-accent-bright border-info/30",
  PAUSED: "bg-slate/15 text-slate border-slate/30",
  VERIFYING: "bg-teal/15 text-teal border-teal/30",
  COMPLETED: "bg-success/15 text-success border-success/30",
  STOPPED: "bg-slate/15 text-fg-muted border-border-strong",
  FAILED: "bg-danger/15 text-danger border-danger/30",
};

export const CASE_STATUS_STYLE: Record<string, string> = {
  DRAFT: "bg-slate/10 text-fg-muted border-border-strong",
  ACTIVE: "bg-info/15 text-accent-bright border-info/30",
  PAUSED: "bg-slate/15 text-slate border-slate/30",
  COMPLETED: "bg-success/15 text-success border-success/30",
  ARCHIVED: "bg-slate/10 text-fg-subtle border-border",
};

export const PRIORITY_STYLE: Record<string, string> = {
  LOW: "text-fg-subtle",
  MEDIUM: "text-fg-muted",
  HIGH: "text-warning",
  CRITICAL: "text-danger",
};

export const HEALTH_STYLE: Record<string, { dot: string; chip: string }> = {
  ONLINE: { dot: "bg-success", chip: "bg-success/15 text-success border-success/30" },
  DEGRADED: { dot: "bg-warning", chip: "bg-warning/15 text-warning border-warning/30" },
  OFFLINE: { dot: "bg-danger", chip: "bg-danger/15 text-danger border-danger/30" },
  OPTIONAL: { dot: "bg-slate", chip: "bg-slate/15 text-slate border-slate/30" },
  NOT_CONFIGURED: { dot: "bg-fg-subtle", chip: "bg-slate/10 text-fg-muted border-border-strong" },
};

export const STAGE_STYLE: Record<string, string> = {
  PLAN: "text-violet border-violet/30",
  SEARCH: "text-accent-bright border-info/30",
  NEWS: "text-accent-bright border-info/30",
  DNS: "text-teal border-teal/30",
  RDAP: "text-teal border-teal/30",
  CT: "text-teal border-teal/30",
  WEB: "text-teal border-teal/30",
  IP: "text-teal border-teal/30",
  GITHUB: "text-fg border-border-strong",
  REDDIT: "text-warning border-warning/30",
  SOCIAL: "text-warning border-warning/30",
  ARCHIVE: "text-slate border-slate/30",
  DOCS: "text-slate border-slate/30",
  VERIFY: "text-success border-success/30",
  GRAPH: "text-violet border-violet/30",
  AI: "text-violet border-violet/30",
  SYSTEM: "text-fg-muted border-border-strong",
};

/** Entity type → icon color; icons themselves are picked in components. */
export const ENTITY_TYPE_COLOR: Record<string, string> = {
  PERSON: "#f59e0b",
  USERNAME: "#fbbf24",
  EMAIL: "#60a5fa",
  DOMAIN: "#14b8a6",
  IP: "#2dd4bf",
  URL: "#38bdf8",
  ORGANIZATION: "#a78bfa",
  COMPANY: "#a78bfa",
  LOCATION: "#34d399",
  PHONE: "#60a5fa",
  SOCIAL_ACCOUNT: "#fb923c",
  REPOSITORY: "#e2e8f0",
  DOCUMENT: "#94a3b8",
  ARTICLE: "#94a3b8",
  EVENT: "#f472b6",
  CRYPTO_ADDRESS: "#facc15",
};

export const TARGET_TYPES = [
  "DOMAIN",
  "IP",
  "EMAIL",
  "USERNAME",
  "ORGANIZATION",
  "PERSON",
  "SOCIAL_ACCOUNT",
  "URL",
  "COMPANY",
  "DOCUMENT",
  "CRYPTO_ADDRESS",
  "PHONE",
];

export const EVIDENCE_TYPES = [
  "DIRECT_STATEMENT",
  "TECHNICAL_RECORD",
  "DOCUMENT",
  "PUBLIC_STATEMENT",
  "ALLEGATION",
  "SYSTEM_INTERPRETATION",
  "ARCHIVE_SNAPSHOT",
  "SCREENSHOT",
];

export const SOURCE_TYPES = [
  "WEBSITE",
  "SEARCH_RESULT",
  "NEWS",
  "SOCIAL",
  "FORUM",
  "CODE_REPOSITORY",
  "TECHNICAL_RECORD",
  "ARCHIVE",
  "DOCUMENT",
  "API",
  "OTHER",
];
