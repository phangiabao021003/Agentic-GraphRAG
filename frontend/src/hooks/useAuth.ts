import { useCallback, useEffect, useState } from "react";
import { apiJson, clearTokens, getRefreshToken, hasTokens, setTokens } from "../api/client";
import type { TokenPair, User } from "../api/types";

/** user === undefined -> checking stored token; null -> logged out. */
export function useAuth() {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
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

  return { user, login, register, logout };
}
