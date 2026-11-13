import type { Metadata } from "next";
import Link from "next/link";

import { LoginForm } from "@/components/auth/login-form";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to your EventDesk account.",
};

export default function LoginPage() {
  return (
    <>
      <h1 className="text-page-title tracking-tight">Sign in</h1>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        Welcome back. Enter your details to continue.
      </p>

      <div className="mt-8">
        <LoginForm />
      </div>

      <p className="mt-6 text-sm text-muted-foreground">
        New to EventDesk?{" "}
        <Link
          href="/register"
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Create an account
        </Link>
      </p>
    </>
  );
}
