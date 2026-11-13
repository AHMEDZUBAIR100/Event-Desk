"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { toast } from "sonner";

import {
  logout as logoutRequest,
  restoreSession,
} from "@/lib/api/auth";
import type { AuthSession, UserRead } from "@/lib/api/types";
import { ApiError, SESSION_UPDATED_EVENT } from "@/lib/api/client";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "@/lib/auth/session";

type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  user: UserRead | null;
  status: AuthStatus;
  login: (auth: AuthSession) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserRead | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let cancelled = false;

    restoreSession()
      .then((session) => {
        if (cancelled) {
          return;
        }

        if (!session) {
          setUser(null);
          setStatus("anonymous");
          return;
        }

        setAccessToken(session.access_token, session.expires_in);
        setUser(session.user);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) {
          return;
        }

        setUser(null);
        setStatus("anonymous");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function handleSessionUpdate(event: Event) {
      const detail = (event as CustomEvent<UserRead | null>).detail;

      if (detail) {
        setUser(detail);
        setStatus("authenticated");
      } else {
        clearAccessToken();
        setUser(null);
        setStatus("anonymous");
      }
    }

    window.addEventListener(SESSION_UPDATED_EVENT, handleSessionUpdate);
    return () =>
      window.removeEventListener(SESSION_UPDATED_EVENT, handleSessionUpdate);
  }, []);

  const login = useCallback((auth: AuthSession) => {
    setAccessToken(auth.access_token, auth.expires_in);
    setUser(auth.user);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutRequest(getAccessToken());
    } catch (error) {
      // The server did not confirm the revocation. Keep the local session and
      // the HttpOnly cookie intact so the user can retry.
      toast.error(
        error instanceof ApiError
          ? error.message
          : "Could not sign out. Please try again.",
      );
      return;
    }

    clearAccessToken();
    setUser(null);
    setStatus("anonymous");
    window.dispatchEvent(
      new CustomEvent(SESSION_UPDATED_EVENT, { detail: null }),
    );
  }, []);

  const value = useMemo(
    () => ({ user, status, login, logout }),
    [user, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}
