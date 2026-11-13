import {
  ApiError,
  apiFetch,
  readErrorMessage,
} from "@/lib/api/client";
import type {
  AuthSession,
  LoginRequest,
  RegisterRequest,
  UserRead,
} from "@/lib/api/types";

async function authRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function login(payload: LoginRequest): Promise<AuthSession> {
  return authRequest<AuthSession>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function register(payload: RegisterRequest): Promise<UserRead> {
  return apiFetch<UserRead>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

let restoreInFlight: Promise<AuthSession | null> | null = null;

async function restoreSessionInternal(): Promise<AuthSession | null> {
  try {
    return await authRequest<AuthSession>("/api/auth/session", {
      method: "POST",
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }

    throw error;
  }
}

export function restoreSession(): Promise<AuthSession | null> {
  if (!restoreInFlight) {
    restoreInFlight = restoreSessionInternal().finally(() => {
      restoreInFlight = null;
    });
  }

  return restoreInFlight;
}

export async function logout(accessToken: string | null): Promise<void> {
  const headers = new Headers();

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch("/api/auth/logout", {
    method: "POST",
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response));
  }
}

export function getMe(): Promise<UserRead> {
  return apiFetch<UserRead>("/users/me");
}
