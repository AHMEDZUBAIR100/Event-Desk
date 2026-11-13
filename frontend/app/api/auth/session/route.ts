import type { NextRequest } from "next/server";
import type { NextResponse } from "next/server";

import { rotateSessionFromCookie } from "@/lib/server/auth";

export async function POST(request: NextRequest): Promise<NextResponse> {
  return rotateSessionFromCookie(request);
}
