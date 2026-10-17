import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiJson, clearTokens, setTokens } from "./client";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiJson auth handling", () => {
  beforeEach(() => {
    setTokens("old-access", "old-refresh");
  });

  afterEach(() => {
    clearTokens();
    vi.restoreAllMocks();
  });

  it("attaches the bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiJson("/me");

    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>)["Authorization"]).toBe("Bearer old-access");
  });

  it("on 401 refreshes once and retries with the new token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401)) // original call
      .mockResolvedValueOnce(jsonResponse({ access_token: "new-access", refresh_token: "new-refresh" })) // refresh
      .mockResolvedValueOnce(jsonResponse({ id: "u1" })); // retry
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiJson("/me");

    expect(result).toEqual({ id: "u1" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const retryInit = fetchMock.mock.calls[2][1];
    expect((retryInit.headers as Record<string, string>)["Authorization"]).toBe("Bearer new-access");
    expect(localStorage.getItem("nva_refresh")).toBe("new-refresh");
  });

  it("clears tokens and fires auth-expired when refresh fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: "Invalid refresh token" }, 401));
    vi.stubGlobal("fetch", fetchMock);
    const expired = vi.fn();
    window.addEventListener("auth-expired", expired);

    await expect(apiJson("/me")).rejects.toThrow();

    expect(localStorage.getItem("nva_access")).toBeNull();
    expect(expired).toHaveBeenCalled();
  });

  it("two concurrent 401s share a single refresh call", async () => {
    let refreshCalls = 0;
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).endsWith("/auth/refresh")) {
        refreshCalls += 1;
        await new Promise((r) => setTimeout(r, 20));
        return jsonResponse({ access_token: "new-access", refresh_token: "new-refresh" });
      }
      const auth = (init?.headers as Record<string, string>)?.["Authorization"];
      // old token → 401; the retry carries the refreshed token → 200
      return auth === "Bearer new-access"
        ? jsonResponse({ ok: true })
        : jsonResponse({ detail: "expired" }, 401);
    });
    vi.stubGlobal("fetch", fetchMock);

    await Promise.all([apiJson("/a"), apiJson("/b")]);

    expect(refreshCalls).toBe(1);
  });
});
