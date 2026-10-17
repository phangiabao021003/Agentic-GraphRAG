// Google sign-in handoff. Pure logic — no React imports.
import { API_URL, ApiError, setTokens } from "./client";
import type { TokenPair } from "./types";

export function googleLoginUrl(): string {
  return `${API_URL}/auth/google/login`;
}

export type GoogleRedirect = { code: string } | { error: string } | null;

/** Backend redirects back with ?google_login=<one-time code> or ?google_error=<reason>. */
export function readGoogleRedirect(search: string): GoogleRedirect {
  const params = new URLSearchParams(search);
  const code = params.get("google_login");
  if (code) return { code };
  const error = params.get("google_error");
  if (error) return { error };
  return null;
}

export async function exchangeGoogleCode(code: string): Promise<void> {
  const resp = await fetch(`${API_URL}/auth/google/exchange`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!resp.ok) throw new ApiError(resp.status, "Google sign-in code exchange failed");
  const pair = (await resp.json()) as TokenPair;
  setTokens(pair.access_token, pair.refresh_token);
}

const MESSAGES: Record<string, string> = {
  denied: "Bạn đã hủy đăng nhập bằng Google.",
  invalid_state: "Phiên đăng nhập Google đã hết hạn. Vui lòng thử lại.",
  unverified_email: "Email Google của bạn chưa được xác minh.",
  failed: "Đăng nhập bằng Google thất bại. Vui lòng thử lại.",
};

export function googleErrorMessage(reason: string): string {
  return MESSAGES[reason] ?? MESSAGES.failed;
}
