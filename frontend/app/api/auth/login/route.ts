import { NextResponse, type NextRequest } from "next/server";

import {
  backendAuthFetch,
  forwardBackendError,
  sessionResponse,
  type BackendAuthResponse,
} from "@/lib/server/auth";

type LoginBody = {
  email?: unknown;
  password?: unknown;
};

export async function POST(request: NextRequest): Promise<NextResponse> {
  let body: LoginBody | null;

  try {
    body = (await request.json()) as LoginBody;
  } catch {
    return NextResponse.json(
      { detail: "A JSON request body is required." },
      { status: 400 },
    );
  }

  if (
    !body ||
    typeof body.email !== "string" ||
    !body.email.trim() ||
    typeof body.password !== "string" ||
    !body.password
  ) {
    return NextResponse.json(
      { detail: "Email and password are required." },
      { status: 400 },
    );
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendAuthFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: body.email,
        password: body.password,
      }),
    });
  } catch {
    return NextResponse.json(
      { detail: "Authentication service is unavailable." },
      { status: 503 },
    );
  }

  if (!backendResponse.ok) {
    return forwardBackendError(backendResponse);
  }

  const auth = (await backendResponse.json()) as BackendAuthResponse;
  return sessionResponse(auth);
}
