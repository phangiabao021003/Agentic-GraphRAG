import { afterEach, describe, expect, it, vi } from "vitest";
import { clearTokens, getAccessToken, getRefreshToken } from "./client";
import { exchangeGoogleCode, googleErrorMessage, readGoogleRedirect } from "./googleLogin";

describe("readGoogleRedirect", () => {
  it("finds a login code", () => {
    expect(readGoogleRedirect("?google_login=abc")).toEqual({ code: "abc" });
  });
  it("finds an error", () => {
    expect(readGoogleRedirect("?google_error=denied")).toEqual({ error: "denied" });
  });
  it("ignores unrelated params", () => {
    expect(readGoogleRedirect("?google=connected")).toBeNull();
  });
});

describe("exchangeGoogleCode", () => {
  afterEach(() => {
    clearTokens();
    vi.restoreAllMocks();
  });

  it("posts the code and stores the returned pair", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ access_token: "a1", refresh_token: "r1" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await exchangeGoogleCode("abc");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/auth\/google\/exchange$/);
    expect(JSON.parse(init.body)).toEqual({ code: "abc" });
    expect(getAccessToken()).toBe("a1");
    expect(getRefreshToken()).toBe("r1");
  });

  it("throws and stores nothing on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 401 })));
    await expect(exchangeGoogleCode("bad")).rejects.toThrow();
    expect(getAccessToken()).toBeNull();
  });
});

it("maps error reasons to Vietnamese messages with a fallback", () => {
  expect(googleErrorMessage("denied")).toMatch(/hủy/);
  expect(googleErrorMessage("something-else")).toBe(googleErrorMessage("failed"));
});
