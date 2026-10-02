// Hand-written from packages/schemas/openapi.json. Untyped (dict) responses are
// modelled from the FastAPI route implementations and marked as such.

export type Confidence =
  | "CONFIRMED"
  | "CORROBORATED"
  | "SUPPORTED"
  | "POSSIBLE"
  | "INFERENCE"
  | "UNVERIFIED"
  | "CONTRADICTED";

export type ReviewState = "PENDING" | "ACCEPTED" | "REJECTED" | "NEEDS_VERIFICATION";

export type CaseStatus = "DRAFT" | "ACTIVE" | "PAUSED" | "COMPLETED" | "ARCHIVED";
export type Priority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type InvestigationStatus =
  | "DRAFT"
  | "PLANNING"
  | "AWAITING_APPROVAL"
  | "RUNNING"
  | "PAUSED"
  | "VERIFYING"
  | "COMPLETED"
  | "STOPPED"
  | "FAILED";

export type TaskStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED" | "DISABLED";

export type ComponentStatus = "ONLINE" | "OFFLINE" | "DEGRADED" | "OPTIONAL" | "NOT_CONFIGURED";

export interface ApiErrorBody {
  code: string;
  message: string;
  detail?: unknown;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface OkResponse {
  ok: boolean;
  message: string;
}

// --- auth ---------------------------------------------------------------

export interface UserOut {
  id: string;
  email: string;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface SessionOut {
  user: UserOut;
  csrf_token: string;
  expires_at: string;
}

export interface SetupStatus {
  needs_setup: boolean;
  user_count: number;
}

export interface SetupRequest {
  email: string;
  username: string;
  password: string;
  display_name?: string;
}

export interface LoginRequest {
  identifier: string;
  password: string;
}

export interface CreateUserRequest {
  email: string;
  username: string;
  password: string;
  display_name?: string;
  role?: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

// --- health -------------------------------------------------------------

export interface HealthComponent {
  name: string;
  status: ComponentStatus;
  message: string;
  latency_ms: number | null;
  detail: Record<string, unknown>;
  optional: boolean;
}

export interface HealthResponse {
  status: ComponentStatus;
  version: string;
  environment: string;
  job_backend: string;
  graph_backend: string;
  components: HealthComponent[];
}

// --- cases --------------------------------------------------------------

export interface TargetOut {
  id: string;
  case_id: string;
  type: string;
  value: string;
  normalized_value: string;
  label: string;
  notes: string;
  is_primary: boolean;
  entity_id: string | null;
  extra: Record<string, unknown>;
  created_at: string;
}

export interface TargetCreate {
  value: string;
  label?: string;
  type?: string | null;
  is_primary?: boolean;
  notes?: string;
}

export interface CaseOut {
  id: string;
  display_id: string;
  name: string;
  description: string;
  objective: string;
  status: CaseStatus | string;
  priority: Priority | string;
  tags: unknown[];
  analyst_id: string | null;
  is_demo: boolean;
  classification: string;
  cloned_from_id: string | null;
  closed_at: string | null;
  evidence_count: number;
  source_count: number;
  entity_count: number;
  finding_count: number;
  created_at: string;
  updated_at: string;
}

export interface CaseDetail extends CaseOut {
  targets: TargetOut[];
}

export interface CaseCreate {
  name: string;
  description?: string;
  objective?: string;
  priority?: string;
  tags?: string[];
  targets?: string[];
  classification?: string;
}

export interface CaseUpdate {
  name?: string | null;
  description?: string | null;
  objective?: string | null;
  status?: string | null;
  priority?: string | null;
  tags?: string[] | null;
  classification?: string | null;
}

export interface NoteOut {
  id: string;
  case_id: string;
  author_id: string | null;
  title: string;
  body: string;
  pinned: boolean;
  entity_refs: unknown[];
  evidence_refs: unknown[];
  created_at: string;
  updated_at: string;
}

export interface NoteCreate {
  title?: string;
  body: string;
  pinned?: boolean;
}

// --- investigations -----------------------------------------------------

export interface TaskOut {
  id: string;
  order: number;
  task_type: string;
  title: string;
  rationale: string;
  status: TaskStatus | string;
  enabled: boolean;
  category: string;
  params: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  error: string | null;
  attempts: number;
  started_at: string | null;
  finished_at: string | null;
}

/** Shape of `InvestigationOut.plan` (planner.Plan.to_dict). */
export interface PlanDict {
  objective?: string;
  target_type?: string;
  target_value?: string;
  branches?: string[];
  source?: string;
  rationale?: string;
  tasks?: unknown[];
}

export interface InvestigationOut {
  id: string;
  display_id: string;
  case_id: string;
  name: string;
  request_text: string;
  objective: string;
  status: InvestigationStatus | string;
  plan: PlanDict;
  plan_rationale: string;
  plan_source: string;
  bounds: Record<string, unknown>;
  stats: Record<string, unknown>;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  approved_at: string | null;
  event_seq: number;
  created_at: string;
  updated_at: string;
}

export interface InvestigationDetail extends InvestigationOut {
  tasks: TaskOut[];
}

export interface InvestigationStart {
  case_id: string;
  request_text?: string;
  target_id?: string | null;
  name?: string | null;
  bounds?: Record<string, number> | null;
  use_ai?: boolean;
  auto_approve?: boolean;
}

export interface TaskChange {
  id: string;
  enabled?: boolean | null;
  params?: Record<string, unknown> | null;
}

export interface PlanUpdate {
  tasks: TaskChange[];
}

export interface ControlRequest {
  action: "pause" | "resume" | "stop";
}

/** GET /investigations/{id}/status (untyped in the spec; from services.investigations.status_summary). */
export interface InvestigationStatusSummary {
  id: string;
  display_id: string;
  status: InvestigationStatus | string;
  objective: string;
  progress: number;
  completeness: Record<string, number>;
  active_task: { id: string; title: string; type: string } | null;
  completed_tasks: string[];
  failed_tasks: { title: string; error: string | null }[];
  remaining_tasks: string[];
  sources_discovered: number;
  entities_discovered: number;
  evidence_collected: number;
  findings: number;
  warnings: string[];
  errors: string[];
  estimated_remaining_tasks: number;
  started_at: string | null;
  finished_at: string | null;
  plan_source: string;
  bounds: Record<string, unknown>;
  stats: Record<string, unknown>;
}

export interface EventOut {
  id: string;
  investigation_id: string;
  case_id: string;
  seq: number;
  created_at: string;
  event_type: string;
  stage: string;
  message: string;
  level: string;
  task_id: string | null;
  data: Record<string, unknown>;
}

export type TaskCatalogue = Record<string, { title: string; category: string; stage: string }>;

// --- sources / evidence -------------------------------------------------

export interface SourceOut {
  id: string;
  display_id: string;
  case_id: string;
  source_type: string;
  url: string;
  canonical_url: string;
  domain: string;
  title: string;
  publisher: string;
  author: string;
  published_at: string | null;
  collected_at: string;
  collector: string;
  tier: number;
  reliability_note: string;
  status: string;
  is_demo: boolean;
  metadata?: Record<string, unknown>;
}

export interface SnapshotOut {
  id: string;
  source_id: string;
  retrieved_at: string;
  http_status: number | null;
  content_type: string;
  title: string;
  content_hash: string;
  text_chars: number;
  artifact_path: string | null;
  final_url: string | null;
  fetch_ms: number | null;
  truncated: boolean;
  metadata?: Record<string, unknown>;
}

export interface SnapshotDetail extends SnapshotOut {
  text_content: string;
}

export interface SourceDetail extends SourceOut {
  snapshots: SnapshotOut[];
  evidence_count: number;
}

/** GET /sources/{id}/compare (untyped in the spec). */
export interface SnapshotCompare {
  changed: boolean;
  message?: string;
  from?: string;
  to?: string;
  title_changed?: boolean;
  old_title?: string;
  new_title?: string;
  diff?: string[];
}

export interface ArtifactOut {
  id: string;
  kind: string;
  path: string;
  mime_type: string;
  sha256: string;
  size_bytes: number;
  original_url: string | null;
  created_at: string;
}

export interface EvidenceOut {
  id: string;
  display_id: string;
  case_id: string;
  investigation_id: string | null;
  source_id: string | null;
  snapshot_id: string | null;
  evidence_type: string;
  claim: string;
  excerpt: string;
  excerpt_verified: boolean;
  context: string;
  collector: string;
  collection_method: string;
  collected_at: string;
  observed_at: string | null;
  confidence: Confidence | string;
  review_state: ReviewState | string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string;
  content_hash: string;
  structured: Record<string, unknown>;
  entity_ids: unknown[];
  is_demo: boolean;
  redacted: boolean;
  created_at: string;
}

export interface EvidenceDetail extends EvidenceOut {
  source: SourceOut | null;
  artifacts: ArtifactOut[];
  // The API types these as plain dicts; entity rows mirror EntityOut and finding rows mirror FindingOut.
  entities: Partial<EntityOut>[];
  findings: Partial<FindingOut>[];
}

export interface ReviewRequest {
  state: ReviewState;
  note?: string;
}

// --- entities / relationships -----------------------------------------

export interface EntityOut {
  id: string;
  display_id: string;
  case_id: string;
  type: string;
  value: string;
  normalized_value: string;
  label: string;
  first_seen: string;
  last_seen: string;
  confidence: Confidence | string;
  source_count: number;
  evidence_ids: unknown[];
  attributes: Record<string, unknown>;
  is_target: boolean;
  is_demo: boolean;
  created_at: string;
}

export interface RelationshipOut {
  id: string;
  display_id: string;
  case_id: string;
  source_entity_id: string;
  target_entity_id: string;
  type: string;
  confidence: Confidence | string;
  rationale: string;
  review_state: ReviewState | string;
  review_note: string;
  attributes: Record<string, unknown>;
  is_demo: boolean;
  created_at: string;
}

/** GET /entities/{id} (untyped in the spec). */
export interface EntityDetail {
  entity: EntityOut;
  aliases: { alias: string; type: string }[];
  relationships: RelationshipOut[];
  evidence: EvidenceOut[];
}

export interface ConfidenceRationale {
  label: string;
  reasons: string[];
  supporting: string[];
  contradicting: string[];
  independent_sources: number;
  best_tier: number | null;
  source_quality: string;
}

export interface RelationshipWhyStep {
  evidence_id: string;
  claim: string;
  source_url: string | null;
  collector: string;
  collected_at: string;
  role: string;
}

export interface RelationshipWhy {
  question: string;
  rationale: string;
  confidence: ConfidenceRationale;
  chain: RelationshipWhyStep[];
}

export interface RelationshipDetail extends RelationshipOut {
  evidence: Partial<EvidenceOut>[];
  source_entity: EntityOut | null;
  target_entity: EntityOut | null;
  why: RelationshipWhy;
}

export interface GraphNode {
  id: string;
  display_id: string;
  type: string;
  label: string;
  value: string;
  confidence: Confidence | string;
  is_target: boolean;
  evidence_count: number;
  attributes?: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  display_id: string;
  source: string;
  target: string;
  type: string;
  confidence: Confidence | string;
  review_state: ReviewState | string;
  evidence_count: number;
  rationale: string;
}

export interface GraphOut {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats?: Record<string, unknown>;
}

// --- findings / timeline -----------------------------------------------

export interface FindingOut {
  id: string;
  display_id: string;
  case_id: string;
  investigation_id: string | null;
  title: string;
  claim: string;
  assessment: string;
  category: string;
  confidence: Confidence | string;
  confidence_rationale: Partial<ConfidenceRationale>;
  proposed_by: string;
  review_state: ReviewState | string;
  review_note: string;
  entity_ids: unknown[];
  relationship_ids: unknown[];
  severity: string;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
}

export interface FindingEvidenceSource {
  display_id: string;
  url: string;
  title: string;
  tier: number;
  domain: string;
  collected_at: string;
}

export interface FindingEvidenceRow extends EvidenceOut {
  source: FindingEvidenceSource | null;
}

export interface FindingDetail extends FindingOut {
  supporting: FindingEvidenceRow[];
  contradicting: FindingEvidenceRow[];
}

export interface WhyChainStep {
  step: number;
  evidence_id: string;
  role: string;
  claim: string;
  excerpt: string;
  excerpt_verified: boolean;
  evidence_type: string;
  collector: string;
  collected_at: string;
  review_state: ReviewState | string;
  source: FindingEvidenceSource | null;
}

export interface WhyOut {
  finding: FindingOut;
  confidence: ConfidenceRationale;
  chain: WhyChainStep[];
  reasoning: string;
}

export interface TimelineOut {
  id: string;
  case_id: string;
  occurred_at: string;
  precision: string;
  title: string;
  description: string;
  event_kind: string;
  evidence_id: string | null;
  entity_ids: unknown[];
  confidence: Confidence | string;
  is_demo: boolean;
}

// --- system -------------------------------------------------------------

/** GET /dashboard (untyped in the spec; from api/v1/system.py). */
export interface DashboardOut {
  cases: { total: number; by_status: Record<string, number> };
  investigations: { total: number; by_status: Record<string, number> };
  evidence: number;
  sources: number;
  entities: number;
  relationships: number;
  findings: number;
  unread_alerts: number;
  source_distribution: Record<string, number>;
  source_tiers: Record<string, number>;
  finding_confidence: Record<string, number>;
  entity_types: Record<string, number>;
  recent_findings: {
    id: string;
    display_id: string;
    case_id: string;
    title: string;
    confidence: Confidence | string;
    created_at: string;
  }[];
  recent_events: {
    id: string;
    investigation_id: string;
    case_id: string;
    created_at: string;
    event_type: string;
    stage: string;
    message: string;
    level: string;
  }[];
  active_investigations: {
    id: string;
    display_id: string;
    case_id: string;
    name: string;
    status: InvestigationStatus | string;
    updated_at: string;
  }[];
}

export interface AuditItem {
  id: string;
  created_at: string;
  actor: string;
  action: string;
  case_id: string | null;
  object_type: string | null;
  object_id: string | null;
  request_id: string | null;
  detail: Record<string, unknown> | null;
}

export type AuditPage = Page<AuditItem>;

export interface SettingsView {
  env: Record<string, unknown>;
  overrides: Record<string, unknown>;
  editable: string[];
  note: string;
}

export interface CollectorInfo {
  name: string;
  description: string;
  tier: number;
  targets: string[];
  stage: string;
  requires_internet: boolean;
  health: { name: string; status: string; message: string; latency_ms: number | null } | null;
}

// --- search (api/v1/search.py; responses are untyped dicts in the spec) ------

export type SearchCategory = "general" | "news" | "code" | "social" | "documents";

export interface SearchResultOut {
  id: string | null;
  query_id?: string;
  case_id?: string;
  rank: number;
  title: string;
  url: string;
  canonical_url: string;
  domain: string;
  snippet: string;
  published_at: string | null;
  collected_at?: string;
  engine: string;
  relevance: number;
  status: string;
  source_id: string | null;
  entities?: { type: string; value: string }[];
}

export interface SearchResponse {
  query_id: string | null;
  provider: string;
  cache_hit: boolean;
  elapsed_ms: number | null;
  warnings: string[];
  results: SearchResultOut[];
}

export interface SearchProviders {
  health: { status: string; message: string; configured?: string[]; problems?: string[] };
  providers: { name: string; configured: boolean; note: string }[];
}

export interface SearchBranch {
  name: string;
  query: string;
  category: string;
}

export interface ResultActionOut {
  result_id: string;
  action: string;
  source_id?: string;
  evidence_id?: string;
  evidence_display_id?: string;
  target_id?: string;
  note?: string;
}

export interface CaseSearchQuery {
  id: string;
  branch: string;
  query: string;
  provider: string;
  status: string;
  enabled: boolean;
  result_count: number;
  error: string | null;
  executed_at: string | null;
  cache_hit: boolean;
  created_at: string;
}

// --- AI analyst (api/v1/ai.py) -------------------------------------------

export interface AIIntent {
  kind: string;
  filters: Record<string, unknown>;
  route: string;
  explanation: string;
}

export interface AIPassage {
  ref: string;
  kind: "evidence" | "finding" | "note" | "snapshot" | "entity" | string;
  text: string;
  score?: number;
  meta: Record<string, unknown>;
}

export interface AIAnswer {
  answer: string;
  citations: AIPassage[];
  passages: AIPassage[];
  uncited_sentences: string[];
  model: string | null;
}

export interface AIQueryResponse {
  intent: AIIntent;
  answer?: AIAnswer;
}

export interface AIModels {
  available: boolean;
  configured: string;
  models: { name: string; size_gb: number; family: string | null; parameters: string | null }[];
}

export interface DraftFindingsOut {
  created: number;
  rejected?: number;
  finding_ids?: string[];
  note?: string;
  skipped?: boolean;
}

// --- reports / exports / imports (api/v1/reports.py, imports.py) --------

export type ReportFormat = "markdown" | "html" | "pdf" | "docx";
export type ReportStatus = "PENDING" | "GENERATING" | "READY" | "FAILED";

export interface ReportOut {
  id: string;
  display_id: string;
  case_id: string;
  title: string;
  format: ReportFormat | string;
  classification: string;
  status: ReportStatus | string;
  file_path: string | null;
  sha256: string | null;
  size_bytes: number | null;
  generated_at: string | null;
  generation_ms: number | null;
  stats: Record<string, unknown>;
  error: string | null;
  created_at: string;
}

export interface ReportDetail extends ReportOut {
  sections: { key: string; title: string; cited_ids: string[] }[];
}

export interface ImportResult {
  entities: number;
  sources: number;
  evidence: number;
  skipped: number;
  kind: string;
}

// --- monitoring (api/v1/monitoring.py) -----------------------------------

export type MonitorCheck = "dns" | "ct" | "search" | "github" | "reddit" | "news";

export interface MonitorNotify {
  telegram?: boolean;
  webhook?: boolean;
  email?: boolean;
  email_to?: string;
}

export interface MonitorOut {
  id: string;
  display_id: string;
  case_id: string;
  name: string;
  target_value: string;
  target_type: string;
  checks: string[];
  schedule: string;
  enabled: boolean;
  keywords: string[];
  notify: MonitorNotify;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
  run_count: number;
  created_at: string;
  has_baseline: boolean;
}

export interface MonitorCreate {
  case_id: string;
  name: string;
  target_id?: string | null;
  target_value?: string | null;
  target_type?: string | null;
  checks?: string[];
  schedule?: string;
  keywords?: string[];
  notify?: MonitorNotify;
}

export interface AlertOut {
  id: string;
  display_id: string;
  case_id: string;
  monitor_id: string | null;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  source_label: string;
  data: Record<string, unknown>;
  read: boolean;
  acknowledged_at: string | null;
  delivered: boolean;
  detected_at: string;
}

export type AlertsPage = Page<AlertOut>;
