import { NextResponse, type NextRequest } from "next/server";

import type { UserRead } from "@/lib/api/types";

export const REFRESH_COOKIE = "eventdesk_refresh";

const REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60;
const API_SERVER_URL = (
  process.env.API_SERVER_URL ??
  process.env.API_PROXY_TARGET ??
  "http://localhost:8000"
).replace(/\/$/, "");

export type BackendAuthResponse = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: UserRead;
};

export type SessionPayload = {
  access_token: string;
  expires_in: number;
  user: UserRead;
};

function secureCookiesEnabled(): boolean {
  return process.env.NODE_ENV === "production";
}

export function setRefreshCookie(
  response: NextResponse,
  refreshToken: string,
): void {
  response.cookies.set({
    name: REFRESH_COOKIE,
    value: refreshToken,
    httpOnly: true,
    secure: secureCookiesEnabled(),
    sameSite: "lax",
    path: "/",
    maxAge: REFRESH_COOKIE_MAX_AGE,
  });
}

export function clearRefreshCookie(response: NextResponse): void {
  response.cookies.set({
    name: REFRESH_COOKIE,
    value: "",
    httpOnly: true,
    secure: secureCookiesEnabled(),
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
}

export function getRefreshToken(request: NextRequest): string | null {
  return request.cookies.get(REFRESH_COOKIE)?.value ?? null;
}

export function getBearerToken(request: NextRequest): string | null {
  const header = request.headers.get("authorization");

  if (!header?.startsWith("Bearer ")) {
    return null;
  }

  return header.slice("Bearer ".length).trim() || null;
}

export function backendAuthFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(`${API_SERVER_URL}/api/v1${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}

export async function forwardBackendError(
  response: Response,
  statusOverride?: number,
): Promise<NextResponse> {
  let detail = "Authentication request failed.";

  try {
    const payload = (await response.json()) as {
      detail?: string | { msg?: string }[];
    };

    if (typeof payload.detail === "string") {
      detail = payload.detail;
    } else if (Array.isArray(payload.detail)) {
      detail = payload.detail
        .map((item) => item.msg)
        .filter(Boolean)
        .join("; ");
    }
  } catch {
    detail = response.statusText || detail;
  }

  return NextResponse.json(
    { detail },
    { status: statusOverride ?? response.status },
  );
}

export function sessionResponse(auth: BackendAuthResponse): NextResponse {
  const response = NextResponse.json<SessionPayload>({
    access_token: auth.access_token,
    expires_in: auth.expires_in,
    user: auth.user,
  });

  setRefreshCookie(response, auth.refresh_token);
  return response;
}

export function noSessionResponse(
  detail = "Session expired. Please sign in again.",
): NextResponse {
  const response = NextResponse.json({ detail }, { status: 401 });
  clearRefreshCookie(response);
  return response;
}

export async function rotateSessionFromCookie(
  request: NextRequest,
): Promise<NextResponse> {
  const refreshToken = getRefreshToken(request);

  if (!refreshToken) {
    return noSessionResponse("No active session.");
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendAuthFetch("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    return NextResponse.json(
      { detail: "Authentication service is unavailable." },
      { status: 503 },
    );
  }

  if (!backendResponse.ok) {
    if (backendResponse.status === 401) {
      return noSessionResponse();
    }

    return forwardBackendError(backendResponse);
  }

  const auth = (await backendResponse.json()) as BackendAuthResponse;
  return sessionResponse(auth);
}
