import type { ApiErrorBody } from "./types";
import { readCookie } from "./utils";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: unknown;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.detail = body.detail;
  }
}

const CSRF_COOKIE = "eyohe_csrf";
const AUTH_PATHS = ["/login", "/setup"];

type Query = Record<string, string | number | boolean | null | undefined>;

export function buildQuery(params?: Query): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  const here = window.location.pathname;
  if (AUTH_PATHS.some((p) => here.startsWith(p))) return;
  const next = encodeURIComponent(here + window.location.search);
  // Full navigation (not router.push) so all in-memory query state is dropped with the session.
  window.location.assign(new URL(`/login?next=${next}`, window.location.origin).toString());
}

async function parseError(res: Response): Promise<ApiError> {
  let body: ApiErrorBody = { code: `http_${res.status}`, message: res.statusText || "Request failed" };
  try {
    const json: unknown = await res.json();
    if (json && typeof json === "object") {
      const j = json as Partial<ApiErrorBody> & { detail?: unknown };
      if (typeof j.message === "string") {
        body = { code: j.code ?? body.code, message: j.message, detail: j.detail };
      } else if (Array.isArray(j.detail)) {
        // FastAPI validation errors arrive as {detail: [{loc, msg}]}.
        const msgs = j.detail
          .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
          .filter(Boolean);
        body = { code: "validation_error", message: msgs.join("; ") || "Validation error", detail: j.detail };
      } else if (typeof j.detail === "string") {
        body = { code: body.code, message: j.detail };
      }
    }
  } catch {
    // Non-JSON error body; keep the status text.
  }
  return new ApiError(res.status, body);
}

interface RequestOptions {
  /** Skip the automatic redirect on 401 (used by the auth guard itself). */
  noRedirect?: boolean;
  signal?: AbortSignal;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  const res = await fetch(`/api/v1${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
    cache: "no-store",
    signal: opts.signal,
  });
  if (res.status === 401 && !opts.noRedirect) {
    redirectToLogin();
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const apiGet = <T>(path: string, params?: Query, opts?: RequestOptions) =>
  request<T>("GET", `${path}${buildQuery(params)}`, undefined, opts);
export const apiPost = <T>(path: string, body?: unknown, opts?: RequestOptions) =>
  request<T>("POST", path, body ?? {}, opts);
export const apiPatch = <T>(path: string, body: unknown, opts?: RequestOptions) =>
  request<T>("PATCH", path, body, opts);
export const apiDelete = <T>(path: string, opts?: RequestOptions) =>
  request<T>("DELETE", path, undefined, opts);

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}
