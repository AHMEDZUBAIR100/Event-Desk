import type { Metadata } from "next";
import Link from "next/link";

import { RegisterForm } from "@/components/auth/register-form";

export const metadata: Metadata = {
  title: "Create account",
  description: "Create your EventDesk account.",
};

export default function RegisterPage() {
  return (
    <>
      <h1 className="text-page-title tracking-tight">Create account</h1>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        Browse events and keep your bookings in one place.
      </p>

      <div className="mt-8">
        <RegisterForm />
      </div>

      <p className="mt-6 text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link
          href="/login"
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Sign in
        </Link>
      </p>
    </>
  );
}
