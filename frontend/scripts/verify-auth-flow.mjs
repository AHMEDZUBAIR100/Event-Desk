import { execFileSync } from "node:child_process";
import { createHmac } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import process from "node:process";

/**
 * End-to-end verification for the EventDesk BFF authentication flow.
 *
 * Requirements:
 *   - FastAPI running on BACKEND_URL (default http://localhost:8000)
 *   - Next.js running on FRONTEND_URL (default http://localhost:3000)
 *   - Docker Postgres container eventdesk-postgres for revocation checks/cleanup
 *
 * Environment overrides:
 *   FRONTEND_URL, BACKEND_URL, SECRET_KEY, EXPECT_SECURE_COOKIE,
 *   POSTGRES_CONTAINER, POSTGRES_USER, POSTGRES_DB
 */

const FRONTEND_URL = (process.env.FRONTEND_URL ?? "http://localhost:3000").replace(
  /\/$/,
  "",
);
const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);
const BACKEND_API = `${BACKEND_URL}/api/v1`;
const REFRESH_COOKIE = "eventdesk_refresh";
const POSTGRES_CONTAINER = process.env.POSTGRES_CONTAINER ?? "eventdesk-postgres";
const POSTGRES_USER = process.env.POSTGRES_USER ?? "eventdesk";
const POSTGRES_DB = process.env.POSTGRES_DB ?? "eventdesk_db";
const EXPECT_SECURE_COOKIE = process.env.EXPECT_SECURE_COOKIE !== "false";
const DEFAULT_SECRET = "replace_with_a_secure_random_secret_key_in_production";

const checks = [];

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function check(name, fn) {
  await fn();
  checks.push(name);
  console.log(`  PASS  ${name}`);
}

function uniqueEmail() {
  return `verify_auth_${Date.now()}_${Math.random().toString(16).slice(2, 8)}@example.com`;
}

function readSecretKey() {
  if (process.env.SECRET_KEY) {
    return process.env.SECRET_KEY;
  }

  for (const candidate of [".env", "../.env", "../backend/.env"]) {
    try {
      const contents = readFileSync(resolve(process.cwd(), candidate), "utf8");
      const line = contents
        .split(/\r?\n/)
        .find((entry) => entry.startsWith("SECRET_KEY="));

      if (line) {
        return line
          .slice("SECRET_KEY=".length)
          .trim()
          .replace(/^["']|["']$/g, "");
      }
    } catch {
      // Try the next location.
    }
  }

  return DEFAULT_SECRET;
}

function base64Url(value) {
  return Buffer.from(value)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function expiredAccessToken(userId, role, secret) {
  const header = base64Url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = base64Url(
    JSON.stringify({
      sub: userId,
      exp: Math.floor(Date.now() / 1000) - 60,
      role,
      type: "access",
    }),
  );
  const data = `${header}.${payload}`;
  const signature = createHmac("sha256", secret)
    .update(data)
    .digest("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

  return `${data}.${signature}`;
}

function setCookieHeaders(response) {
  if (typeof response.headers.getSetCookie === "function") {
    return response.headers.getSetCookie();
  }

  const raw = response.headers.get("set-cookie");
  return raw ? [raw] : [];
}

function findRefreshCookie(response) {
  const header = setCookieHeaders(response).find((value) =>
    value.startsWith(`${REFRESH_COOKIE}=`),
  );

  if (!header) {
    return null;
  }

  const [pair, ...attributes] = header.split(";").map((part) => part.trim());
  const value = decodeURIComponent(pair.slice(`${REFRESH_COOKIE}=`.length));
  const normalized = attributes.map((attribute) => attribute.toLowerCase());

  return {
    header,
    value,
    httpOnly: normalized.includes("httponly"),
    secure: normalized.includes("secure"),
    sameSite: normalized
      .find((attribute) => attribute.startsWith("samesite="))
      ?.slice("samesite=".length),
    path: normalized
      .find((attribute) => attribute.startsWith("path="))
      ?.slice("path=".length),
    maxAge: normalized
      .find((attribute) => attribute.startsWith("max-age="))
      ?.slice("max-age=".length),
  };
}

async function readJson(response) {
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

async function frontend(path, { method = "POST", cookie, accessToken, body } = {}) {
  const headers = new Headers({ Accept: "application/json" });

  if (cookie) {
    headers.set("Cookie", `${REFRESH_COOKIE}=${encodeURIComponent(cookie)}`);
  }

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${FRONTEND_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    redirect: "manual",
  });

  return { response, data: await readJson(response) };
}

async function backendRefresh(refreshToken) {
  const response = await fetch(`${BACKEND_API}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  return response.status;
}

function psql(sql) {
  return execFileSync(
    "docker",
    [
      "exec",
      POSTGRES_CONTAINER,
      "psql",
      "-U",
      POSTGRES_USER,
      "-d",
      POSTGRES_DB,
      "-tAc",
      sql,
    ],
    { encoding: "utf8" },
  ).trim();
}

function activeRefreshTokenCount(email) {
  const escaped = email.replace(/'/g, "''");
  return Number(
    psql(
      `SELECT count(*) FROM refresh_tokens WHERE user_id = (SELECT id FROM users WHERE email = '${escaped}') AND revoked = false;`,
    ),
  );
}

function totalRefreshTokenCount(email) {
  const escaped = email.replace(/'/g, "''");
  return Number(
    psql(
      `SELECT count(*) FROM refresh_tokens WHERE user_id = (SELECT id FROM users WHERE email = '${escaped}');`,
    ),
  );
}

function cleanupUser(email) {
  const escaped = email.replace(/'/g, "''");
  psql(
    `DELETE FROM audit_logs WHERE actor_id IN (SELECT id FROM users WHERE email = '${escaped}'); ` +
      `DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE email = '${escaped}'); ` +
      `DELETE FROM events WHERE organizer_id IN (SELECT id FROM users WHERE email = '${escaped}'); ` +
      `DELETE FROM users WHERE email = '${escaped}';`,
  );
}

async function createTestUser(email) {
  const password = "VerifyAuthPass123!";
  const response = await fetch(`${BACKEND_API}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      full_name: "Auth Flow Verification",
      role: "attendee",
    }),
  });

  assert(
    response.status === 201,
    `Could not create test user (status ${response.status}).`,
  );

  return password;
}

function assertCookieFlags(cookie, label) {
  assert(cookie, `${label}: the BFF did not set ${REFRESH_COOKIE}.`);
  assert(cookie.value, `${label}: the refresh cookie is empty.`);
  assert(cookie.httpOnly, `${label}: refresh cookie is missing HttpOnly.`);
  assert(
    cookie.sameSite === "lax",
    `${label}: refresh cookie SameSite is ${cookie.sameSite ?? "missing"}, expected lax.`,
  );
  assert(cookie.path === "/", `${label}: refresh cookie Path is not /.`);
  if (EXPECT_SECURE_COOKIE) {
    assert(cookie.secure, `${label}: refresh cookie is missing Secure.`);
  }
}

function assertNoRefreshToken(data, label) {
  assert(
    data &&
      typeof data === "object" &&
      !Object.prototype.hasOwnProperty.call(data, "refresh_token"),
    `${label}: BFF response leaked refresh_token to JavaScript.`,
  );
  assert(
    typeof data.access_token === "string" && data.access_token.length > 0,
    `${label}: BFF response did not include an access token.`,
  );
}

async function main() {
  const email = uniqueEmail();
  const secret = readSecretKey();

  console.log(`Verifying auth flow for ${email}`);
  console.log(`  frontend: ${FRONTEND_URL}`);
  console.log(`  backend:  ${BACKEND_URL}`);

  try {
    cleanupUser(email);

    try {
      const backendHealth = await fetch(`${BACKEND_URL}/health`);
      const frontendHealth = await fetch(`${FRONTEND_URL}/events`);
      assert(
        backendHealth.ok,
        `Backend is not healthy at ${BACKEND_URL}/health.`,
      );
      assert(
        frontendHealth.ok,
        `Frontend is not reachable at ${FRONTEND_URL}/events.`,
      );
    } catch (error) {
      throw new Error(
        `Both servers must be running before verification. ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
    }

    const password = await createTestUser(email);

    let loginCookie;
    let loginUser;

    await check("login returns an access token and an HttpOnly refresh cookie", async () => {
      const { response, data } = await frontend("/api/auth/login", {
        body: { email, password },
      });

      assert(response.status === 200, `Login failed with status ${response.status}.`);
      assertNoRefreshToken(data, "Login");
      assert(data.user?.email === email, "Login returned the wrong user.");
      loginUser = data.user;
      loginCookie = findRefreshCookie(response);
      assertCookieFlags(loginCookie, "Login");

      const leaked = JSON.stringify(data).includes("refresh_token");
      assert(!leaked, "Login response body mentions refresh_token.");
    });

    let sessionCookie;

    await check("session restore rotates the cookie and invalidates the previous token", async () => {
      const { response, data } = await frontend("/api/auth/session", {
        cookie: loginCookie.value,
      });

      assert(
        response.status === 200,
        `Session restore failed with status ${response.status}.`,
      );
      assertNoRefreshToken(data, "Session restore");
      sessionCookie = findRefreshCookie(response);
      assertCookieFlags(sessionCookie, "Session restore");
      assert(
        sessionCookie.value !== loginCookie.value,
        "Session restore did not rotate the refresh token.",
      );
      assert(
        (await backendRefresh(loginCookie.value)) === 401,
        "The pre-rotation refresh token is still usable after session restore.",
      );
    });

    let rotatedCookie;
    let rotatedAccessToken;

    await check("refresh rotates again and rejects the previous token", async () => {
      const { response, data } = await frontend("/api/auth/refresh", {
        cookie: sessionCookie.value,
      });

      assert(
        response.status === 200,
        `Refresh failed with status ${response.status}.`,
      );
      assertNoRefreshToken(data, "Refresh");
      rotatedCookie = findRefreshCookie(response);
      rotatedAccessToken = data.access_token;
      assertCookieFlags(rotatedCookie, "Refresh");
      assert(
        rotatedCookie.value !== sessionCookie.value,
        "Refresh did not rotate the refresh token.",
      );
      assert(
        (await backendRefresh(sessionCookie.value)) === 401,
        "The previous refresh token is still usable after rotation.",
      );
    });

    await check("a revoked refresh token cannot be reused", async () => {
      assert(
        (await backendRefresh(loginCookie.value)) === 401,
        "The original refresh token is still usable after two rotations.",
      );
    });

    await check("logout with a valid access token revokes the refresh token", async () => {
      const { response } = await frontend("/api/auth/logout", {
        cookie: rotatedCookie.value,
        accessToken: rotatedAccessToken,
      });

      assert(response.status === 204, `Logout failed with status ${response.status}.`);
      const cleared = findRefreshCookie(response);
      assert(cleared && cleared.maxAge === "0", "Logout did not clear the cookie.");

      assert(
        (await backendRefresh(rotatedCookie.value)) === 401,
        "Logout left the refresh token usable server-side.",
      );
      assert(
        activeRefreshTokenCount(email) === 0,
        "Logout left active refresh-token rows in the database.",
      );
    });

    let expiredLogoutCookie;

    await check(
      "logout with an expired access token rotates first and revokes the token",
      async () => {
        const login = await frontend("/api/auth/login", {
          body: { email, password },
        });
        assert(
          login.response.status === 200,
          `Second login failed with status ${login.response.status}.`,
        );
        expiredLogoutCookie = findRefreshCookie(login.response);
        assertCookieFlags(expiredLogoutCookie, "Expired-token login");

        const expiredToken = expiredAccessToken(
          loginUser.id,
          loginUser.role,
          secret,
        );

        const { response } = await frontend("/api/auth/logout", {
          cookie: expiredLogoutCookie.value,
          accessToken: expiredToken,
        });

        assert(
          response.status === 204,
          `Expired-access logout failed with status ${response.status}.`,
        );
        const cleared = findRefreshCookie(response);
        assert(
          cleared && cleared.maxAge === "0",
          "Expired-access logout did not clear the cookie.",
        );

        assert(
          (await backendRefresh(expiredLogoutCookie.value)) === 401,
          "Expired-access logout left the refresh token usable server-side.",
        );
        assert(
          activeRefreshTokenCount(email) === 0,
          "Expired-access logout left active refresh-token rows in the database.",
        );
        assert(
          totalRefreshTokenCount(email) >= 2,
          "Expected revoked refresh-token rows to remain for the audit trail.",
        );
      },
    );

    await check("post-logout session restore and refresh are rejected", async () => {
      const session = await frontend("/api/auth/session", {
        cookie: expiredLogoutCookie.value,
      });
      assert(session.response.status === 401, "A revoked session was restored.");

      const refresh = await frontend("/api/auth/refresh", {
        cookie: expiredLogoutCookie.value,
      });
      assert(refresh.response.status === 401, "A revoked token was refreshed.");

      const anonymous = await frontend("/api/auth/session");
      assert(
        anonymous.response.status === 401,
        "Session restore without a cookie should return 401.",
      );
    });

    console.log(`\nAll ${checks.length} auth-flow checks passed.`);
  } finally {
    try {
      cleanupUser(email);
    } catch (error) {
      console.warn(
        `Warning: could not clean up ${email}: ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
    }
  }
}

main().catch((error) => {
  console.error(`\nAuth flow verification failed: ${error.message}`);
  process.exitCode = 1;
});
