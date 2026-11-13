import type { AuthSession } from "@/lib/api/types";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "@/lib/auth/session";

const API_BASE = "/api/v1";

export const SESSION_UPDATED_EVENT = "eventdesk:session-updated";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function readErrorMessage(
  response: Response,
): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: string | { msg?: string }[];
    };

    if (typeof payload.detail === "string") {
      return payload.detail;
    }

    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => item.msg)
        .filter(Boolean)
        .join("; ");
    }
  } catch {
    // Fall through to the status text.
  }

  return response.statusText || "Something went wrong. Please try again.";
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch("/api/auth/refresh", {
          method: "POST",
          credentials: "same-origin",
          cache: "no-store",
        });

        if (!response.ok) {
          clearAccessToken();
          window.dispatchEvent(
            new CustomEvent(SESSION_UPDATED_EVENT, { detail: null }),
          );
          return false;
        }

        const auth = (await response.json()) as AuthSession;
        setAccessToken(auth.access_token, auth.expires_in);
        window.dispatchEvent(
          new CustomEvent(SESSION_UPDATED_EVENT, { detail: auth.user }),
        );
        return true;
      } catch {
        clearAccessToken();
        window.dispatchEvent(
          new CustomEvent(SESSION_UPDATED_EVENT, { detail: null }),
        );
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }

  return refreshInFlight;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  allowRetry = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  const accessToken = getAccessToken();

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });

  if (
    response.status === 401 &&
    allowRetry &&
    !path.startsWith("/auth/") &&
    (await refreshAccessToken())
  ) {
    return apiFetch<T>(path, init, false);
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
