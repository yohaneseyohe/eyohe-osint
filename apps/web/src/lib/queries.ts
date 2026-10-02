import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { apiGet } from "./api";
import type {
  AuditPage,
  CaseDetail,
  CaseOut,
  CollectorInfo,
  DashboardOut,
  EntityDetail,
  EntityOut,
  EvidenceDetail,
  EvidenceOut,
  FindingDetail,
  FindingOut,
  GraphOut,
  HealthResponse,
  InvestigationDetail,
  InvestigationOut,
  InvestigationStatusSummary,
  NoteOut,
  Page,
  RelationshipDetail,
  SessionOut,
  SettingsView,
  SetupStatus,
  SnapshotCompare,
  SourceDetail,
  SourceOut,
  TaskCatalogue,
  TimelineOut,
  UserOut,
  WhyOut,
} from "./types";

type Params = Record<string, string | number | boolean | null | undefined>;

// Query keys are centralised so mutations can invalidate precisely.
export const qk = {
  session: ["session"] as const,
  setup: ["setup"] as const,
  health: ["health"] as const,
  dashboard: ["dashboard"] as const,
  cases: (p?: Params) => ["cases", p ?? {}] as const,
  case: (id: string) => ["case", id] as const,
  notes: (id: string) => ["case", id, "notes"] as const,
  investigations: (p?: Params) => ["investigations", p ?? {}] as const,
  investigation: (id: string) => ["investigation", id] as const,
  invStatus: (id: string) => ["investigation", id, "status"] as const,
  taskCatalogue: ["task-catalogue"] as const,
  evidenceList: (caseId: string, p?: Params) => ["case", caseId, "evidence", p ?? {}] as const,
  evidence: (id: string) => ["evidence", id] as const,
  sourcesList: (caseId: string, p?: Params) => ["case", caseId, "sources", p ?? {}] as const,
  source: (id: string) => ["source", id] as const,
  sourceCompare: (id: string) => ["source", id, "compare"] as const,
  entitiesList: (caseId: string, p?: Params) => ["case", caseId, "entities", p ?? {}] as const,
  entity: (id: string) => ["entity", id] as const,
  relationship: (id: string) => ["relationship", id] as const,
  graph: (caseId: string, p?: Params) => ["case", caseId, "graph", p ?? {}] as const,
  findingsList: (caseId: string, p?: Params) => ["case", caseId, "findings", p ?? {}] as const,
  finding: (id: string) => ["finding", id] as const,
  why: (id: string) => ["finding", id, "why"] as const,
  timeline: (caseId: string) => ["case", caseId, "timeline"] as const,
  audit: (p?: Params) => ["audit", p ?? {}] as const,
  settings: ["settings"] as const,
  collectors: ["collectors"] as const,
  users: ["users"] as const,
};

type Opts<T> = Omit<UseQueryOptions<T, Error>, "queryKey" | "queryFn">;

export const useSession = (opts?: Opts<SessionOut>) =>
  useQuery({
    queryKey: qk.session,
    queryFn: () => apiGet<SessionOut>("/auth/me", undefined, { noRedirect: true }),
    retry: false,
    staleTime: 60_000,
    ...opts,
  });

export const useSetupStatus = () =>
  useQuery({ queryKey: qk.setup, queryFn: () => apiGet<SetupStatus>("/auth/setup", undefined, { noRedirect: true }), retry: false });

export const useHealth = (refetchInterval: number | false = 30_000) =>
  useQuery({
    queryKey: qk.health,
    queryFn: () => apiGet<HealthResponse>("/health", undefined, { noRedirect: true }),
    refetchInterval,
    staleTime: 10_000,
  });

export const useDashboard = () =>
  useQuery({ queryKey: qk.dashboard, queryFn: () => apiGet<DashboardOut>("/dashboard"), refetchInterval: 15_000 });

export const useCases = (p?: Params) =>
  useQuery({ queryKey: qk.cases(p), queryFn: () => apiGet<Page<CaseOut>>("/cases", p) });

export const useCase = (id: string | null) =>
  useQuery({ queryKey: qk.case(id ?? ""), queryFn: () => apiGet<CaseDetail>(`/cases/${id}`), enabled: !!id });

export const useNotes = (caseId: string) =>
  useQuery({ queryKey: qk.notes(caseId), queryFn: () => apiGet<NoteOut[]>(`/cases/${caseId}/notes`) });

export const useInvestigations = (p?: Params) =>
  useQuery({
    queryKey: qk.investigations(p),
    queryFn: () => apiGet<InvestigationOut[]>("/investigations", p),
    refetchInterval: 10_000,
  });

const LIVE_STATUSES = new Set(["PLANNING", "RUNNING", "VERIFYING", "PAUSED"]);

export const useInvestigation = (id: string) =>
  useQuery({
    queryKey: qk.investigation(id),
    queryFn: () => apiGet<InvestigationDetail>(`/investigations/${id}`),
    // Poll while the run is live so task states keep up with the SSE feed.
    refetchInterval: (q) => (q.state.data && LIVE_STATUSES.has(q.state.data.status) ? 4_000 : false),
  });

export const useInvestigationStatus = (id: string | null) =>
  useQuery({
    queryKey: qk.invStatus(id ?? ""),
    queryFn: () => apiGet<InvestigationStatusSummary>(`/investigations/${id}/status`),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data && LIVE_STATUSES.has(q.state.data.status) ? 4_000 : 30_000),
  });

export const useTaskCatalogue = () =>
  useQuery({ queryKey: qk.taskCatalogue, queryFn: () => apiGet<TaskCatalogue>("/investigations/task-catalogue"), staleTime: Infinity });

export const useEvidenceList = (caseId: string | null, p?: Params) =>
  useQuery({
    queryKey: qk.evidenceList(caseId ?? "", p),
    queryFn: () => apiGet<Page<EvidenceOut>>(`/cases/${caseId}/evidence`, p),
    enabled: !!caseId,
  });

export const useEvidence = (id: string | null) =>
  useQuery({ queryKey: qk.evidence(id ?? ""), queryFn: () => apiGet<EvidenceDetail>(`/evidence/${id}`), enabled: !!id });

export const useSourcesList = (caseId: string | null, p?: Params) =>
  useQuery({
    queryKey: qk.sourcesList(caseId ?? "", p),
    queryFn: () => apiGet<Page<SourceOut>>(`/cases/${caseId}/sources`, p),
    enabled: !!caseId,
  });

export const useSource = (id: string | null) =>
  useQuery({ queryKey: qk.source(id ?? ""), queryFn: () => apiGet<SourceDetail>(`/sources/${id}`), enabled: !!id });

export const useSourceCompare = (id: string | null, enabled: boolean) =>
  useQuery({
    queryKey: qk.sourceCompare(id ?? ""),
    queryFn: () => apiGet<SnapshotCompare>(`/sources/${id}/compare`),
    enabled: !!id && enabled,
  });

export const useEntitiesList = (caseId: string | null, p?: Params) =>
  useQuery({
    queryKey: qk.entitiesList(caseId ?? "", p),
    queryFn: () => apiGet<Page<EntityOut>>(`/cases/${caseId}/entities`, p),
    enabled: !!caseId,
  });

export const useEntity = (id: string | null) =>
  useQuery({ queryKey: qk.entity(id ?? ""), queryFn: () => apiGet<EntityDetail>(`/entities/${id}`), enabled: !!id });

export const useRelationship = (id: string | null) =>
  useQuery({
    queryKey: qk.relationship(id ?? ""),
    queryFn: () => apiGet<RelationshipDetail>(`/relationships/${id}`),
    enabled: !!id,
  });

export const useGraph = (caseId: string | null, p?: Params) =>
  useQuery({
    queryKey: qk.graph(caseId ?? "", p),
    queryFn: () => apiGet<GraphOut>(`/cases/${caseId}/graph`, p),
    enabled: !!caseId,
  });

export const useFindingsList = (caseId: string | null, p?: Params) =>
  useQuery({
    queryKey: qk.findingsList(caseId ?? "", p),
    queryFn: () => apiGet<Page<FindingOut>>(`/cases/${caseId}/findings`, p),
    enabled: !!caseId,
  });

export const useFinding = (id: string | null) =>
  useQuery({ queryKey: qk.finding(id ?? ""), queryFn: () => apiGet<FindingDetail>(`/findings/${id}`), enabled: !!id });

export const useWhy = (id: string | null, enabled = true) =>
  useQuery({ queryKey: qk.why(id ?? ""), queryFn: () => apiGet<WhyOut>(`/findings/${id}/why`), enabled: !!id && enabled });

export const useTimeline = (caseId: string | null) =>
  useQuery({
    queryKey: qk.timeline(caseId ?? ""),
    queryFn: () => apiGet<TimelineOut[]>(`/cases/${caseId}/timeline`),
    enabled: !!caseId,
  });

export const useAudit = (p?: Params) =>
  useQuery({ queryKey: qk.audit(p), queryFn: () => apiGet<AuditPage>("/audit", p) });

export const useSettings = () =>
  useQuery({ queryKey: qk.settings, queryFn: () => apiGet<SettingsView>("/settings") });

export const useCollectors = () =>
  useQuery({ queryKey: qk.collectors, queryFn: () => apiGet<CollectorInfo[]>("/collectors") });

export const useUsers = (enabled: boolean) =>
  useQuery({ queryKey: qk.users, queryFn: () => apiGet<UserOut[]>("/auth/users"), enabled, retry: false });
