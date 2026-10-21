// Backend HTTP client. Pure logic — this module must never import React.
import type { TokenPair } from "./types";

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const ACCESS_KEY = "nva_access";
const REFRESH_KEY = "nva_refresh";

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

export const NETWORK_ERROR_MESSAGE = "Không kết nối được tới máy chủ";

export type ApiJsonOptions = { notify?: boolean };

/** Tell the UI (ToastProvider listens on window) that a request failed. */
export function notifyApiError(status: number, message: string): void {
  window.dispatchEvent(new CustomEvent("api-error", { detail: { status, message } }));
}

/** Backend error bodies are `{"detail": "..."}` (FastAPI); fall back to a generic line. */
export async function errorDetail(resp: Response): Promise<string> {
  try {
    const body = await resp.json();
    if (body?.detail) return String(body.detail);
  } catch {
    /* non-JSON error body */
  }
  return `Lỗi máy chủ (HTTP ${resp.status})`;
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function hasTokens(): boolean {
  return getAccessToken() !== null;
}

// One shared in-flight refresh: with token rotation, two racing refreshes would
// revoke each other's tokens and log the user out for no reason.
let refreshPromise: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  const refreshToken = localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return false;
  try {
    const resp = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!resp.ok) return false;
    const pair = (await resp.json()) as TokenPair;
    setTokens(pair.access_token, pair.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export async function refreshTokens(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  const token = getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

/** fetch with Bearer + one refresh-and-retry on 401. */
async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const doCall = () =>
    fetch(`${API_URL}${path}`, {
      ...init,
      headers: authHeaders(init.headers as Record<string, string> | undefined),
    });

  let resp = await doCall();
  if (resp.status === 401) {
    const refreshed = await refreshTokens();
    if (refreshed) {
      resp = await doCall();
    }
    if (resp.status === 401) {
      clearTokens();
      window.dispatchEvent(new Event("auth-expired"));
    }
  }
  return resp;
}

export async function apiJson<T = any>(
  path: string,
  init: RequestInit = {},
  opts: ApiJsonOptions = {},
): Promise<T> {
  const notify = opts.notify ?? true;
  const hasBody = init.body !== undefined && !(init.body instanceof FormData);
  let resp: Response;
  try {
    resp = await apiFetch(path, {
      ...init,
      headers: {
        ...(hasBody ? { "Content-Type": "application/json" } : {}),
        ...(init.headers as Record<string, string> | undefined),
      },
    });
  } catch {
    if (notify) notifyApiError(0, NETWORK_ERROR_MESSAGE);
    throw new ApiError(0, NETWORK_ERROR_MESSAGE);
  }
  if (!resp.ok) {
    const detail = await errorDetail(resp);
    // 401 is handled by apiFetch (refresh + auth-expired); never toast it.
    if (notify && resp.status !== 401) notifyApiError(resp.status, detail);
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}
