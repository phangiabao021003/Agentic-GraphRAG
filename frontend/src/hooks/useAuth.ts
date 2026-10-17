import { useCallback, useEffect, useState } from "react";
import { apiJson, clearTokens, getRefreshToken, hasTokens, setTokens } from "../api/client";
import { exchangeGoogleCode, readGoogleRedirect } from "../api/googleLogin";
import type { TokenPair, User } from "../api/types";

/** user === undefined -> checking stored token; null -> logged out. */
export function useAuth() {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [googleError, setGoogleError] = useState<string | null>(null);

  useEffect(() => {
    // Google sign-in lands on ?google_login=<one-time code> or ?google_error=<reason>.
    const redirect = readGoogleRedirect(window.location.search);
    if (redirect) {
      // Drop the one-time code from the address bar and history right away.
      window.history.replaceState(null, "", window.location.pathname);
    }
    if (redirect && "code" in redirect) {
      exchangeGoogleCode(redirect.code)
        .then(() => apiJson<User>("/me"))
        .then(setUser)
        .catch(() => {
          setGoogleError("failed");
          setUser(null);
        });
      return;
    }
    if (redirect && "error" in redirect) setGoogleError(redirect.error);
    if (!hasTokens()) {
      setUser(null);
      return;
    }
    apiJson<User>("/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  useEffect(() => {
    const onExpired = () => setUser(null);
    window.addEventListener("auth-expired", onExpired);
    return () => window.removeEventListener("auth-expired", onExpired);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const pair = await apiJson<TokenPair>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setTokens(pair.access_token, pair.refresh_token);
    setUser(await apiJson<User>("/me"));
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const pair = await apiJson<TokenPair>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setTokens(pair.access_token, pair.refresh_token);
    setUser(await apiJson<User>("/me"));
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      // best-effort server-side revoke; local logout happens regardless
      apiJson("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => {});
    }
    clearTokens();
    setUser(null);
  }, []);

  return { user, login, register, logout, googleError };
}
