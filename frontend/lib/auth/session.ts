const EXPIRY_SKEW_MS = 5_000;

let accessToken: string | null = null;
let accessTokenExpiresAt = 0;

export function setAccessToken(token: string, expiresInSeconds: number): void {
  accessToken = token;
  accessTokenExpiresAt = Date.now() + expiresInSeconds * 1000;
}

export function getAccessToken(): string | null {
  if (!accessToken) {
    return null;
  }

  if (Date.now() >= accessTokenExpiresAt - EXPIRY_SKEW_MS) {
    return null;
  }

  return accessToken;
}

export function clearAccessToken(): void {
  accessToken = null;
  accessTokenExpiresAt = 0;
}
