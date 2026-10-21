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

describe("apiJson error notification", () => {
  beforeEach(() => {
    setTokens("old-access", "old-refresh");
  });

  afterEach(() => {
    clearTokens();
    vi.restoreAllMocks();
  });

  function listen() {
    const received: Array<{ status: number; message: string }> = [];
    const handler = (e: Event) => received.push((e as CustomEvent).detail);
    window.addEventListener("api-error", handler);
    return { received, stop: () => window.removeEventListener("api-error", handler) };
  }

  it("dispatches api-error with the backend detail on a 502", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "mcp-server không phản hồi" }, 502)));
    const { received, stop } = listen();

    await expect(apiJson("/documents")).rejects.toThrow("mcp-server không phản hồi");

    stop();
    expect(received).toEqual([{ status: 502, message: "mcp-server không phản hồi" }]);
  });

  it("falls back to a generic message when the body has no detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("oops", { status: 500 })));
    const { received, stop } = listen();

    await expect(apiJson("/x")).rejects.toThrow();

    stop();
    expect(received).toEqual([{ status: 500, message: "Lỗi máy chủ (HTTP 500)" }]);
  });

  it("does not dispatch api-error for 401 (auth-expired handles it)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
        .mockResolvedValueOnce(jsonResponse({ detail: "Invalid refresh token" }, 401)),
    );
    const { received, stop } = listen();

    await expect(apiJson("/me")).rejects.toThrow();

    stop();
    expect(received).toEqual([]);
  });

  it("dispatches status 0 when fetch itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const { received, stop } = listen();

    await expect(apiJson("/me")).rejects.toThrow("Không kết nối được tới máy chủ");

    stop();
    expect(received).toEqual([{ status: 0, message: "Không kết nối được tới máy chủ" }]);
  });

  it("notify: false suppresses the event but still throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "Email already registered" }, 409)));
    const { received, stop } = listen();

    await expect(apiJson("/auth/register", { method: "POST" }, { notify: false }))
      .rejects.toThrow("Email already registered");

    stop();
    expect(received).toEqual([]);
  });
});
