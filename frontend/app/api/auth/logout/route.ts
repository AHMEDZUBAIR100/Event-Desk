import { NextResponse, type NextRequest } from "next/server";

import {
  backendAuthFetch,
  clearRefreshCookie,
  forwardBackendError,
  getBearerToken,
  getRefreshToken,
  setRefreshCookie,
  type BackendAuthResponse,
} from "@/lib/server/auth";

function loggedOutResponse(): NextResponse {
  const response = new NextResponse(null, { status: 204 });
  clearRefreshCookie(response);
  return response;
}

function unavailableResponse(
  detail = "Logout could not be completed. Please try again.",
  rotatedRefreshToken?: string,
): NextResponse {
  const response = NextResponse.json({ detail }, { status: 503 });

  // Keep the session retryable. If rotation already happened, store the rotated
  // token so a later logout attempt can revoke it.
  if (rotatedRefreshToken) {
    setRefreshCookie(response, rotatedRefreshToken);
  }

  return response;
}

async function revokeRotatedToken(
  rotated: BackendAuthResponse,
): Promise<NextResponse> {
  let logoutResponse: Response;

  try {
    logoutResponse = await backendAuthFetch("/auth/logout", {
      method: "POST",
      headers: { Authorization: `Bearer ${rotated.access_token}` },
      body: JSON.stringify({ refresh_token: rotated.refresh_token }),
    });
  } catch {
    // The rotated token is valid but could not be revoked. Preserve it so the
    // client can retry instead of assuming the session ended.
    return unavailableResponse(undefined, rotated.refresh_token);
  }

  if (logoutResponse.ok) {
    return loggedOutResponse();
  }

  // A freshly issued access token being rejected is an inconsistent backend
  // state, not an expired session. Surface it as a gateway failure.
  const status = logoutResponse.status === 401 ? 502 : undefined;
  const failed = await forwardBackendError(logoutResponse, status);
  setRefreshCookie(failed, rotated.refresh_token);
  return failed;
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const refreshToken = getRefreshToken(request);

  if (!refreshToken) {
    return loggedOutResponse();
  }

  const accessToken = getBearerToken(request);

  if (accessToken) {
    let logoutResponse: Response;

    try {
      logoutResponse = await backendAuthFetch("/auth/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // Network failure: keep the cookie so logout can be retried.
      return unavailableResponse();
    }

    if (logoutResponse.ok) {
      return loggedOutResponse();
    }

    if (logoutResponse.status !== 401) {
      // Do not clear the cookie when the backend did not confirm the revocation.
      return forwardBackendError(logoutResponse);
    }

    // The access token is expired. Fall through to the refresh-then-logout path.
  }

  let refreshResponse: Response;

  try {
    refreshResponse = await backendAuthFetch("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    // Network failure: the original refresh token was not rotated.
    return unavailableResponse();
  }

  if (refreshResponse.status === 401) {
    // Expected: the token is already invalid, expired, or revoked. There is
    // nothing left to revoke server-side, so the local logout can complete.
    return loggedOutResponse();
  }

  if (!refreshResponse.ok) {
    // Any other refresh failure is unexpected; keep the cookie for a retry.
    return forwardBackendError(refreshResponse);
  }

  const rotated = (await refreshResponse.json()) as BackendAuthResponse;
  return revokeRotatedToken(rotated);
}
