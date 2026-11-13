"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { PasswordInput } from "@/components/auth/password-input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { login as loginRequest, register as registerRequest } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-provider";

const registerSchema = z
  .object({
    full_name: z
      .string()
      .trim()
      .min(1, "Enter your name.")
      .max(255, "Use 255 characters or fewer."),
    email: z.string().trim().email("Enter a valid email address."),
    password: z
      .string()
      .min(8, "Use at least 8 characters.")
      .max(128, "Use 128 characters or fewer."),
    confirm_password: z.string().min(1, "Confirm your password."),
    role: z.enum(["attendee", "organizer"]),
  })
  .refine((values) => values.password === values.confirm_password, {
    message: "Passwords do not match.",
    path: ["confirm_password"],
  });

type RegisterValues = z.infer<typeof registerSchema>;

export function RegisterForm() {
  const router = useRouter();
  const { login, status } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      full_name: "",
      email: "",
      password: "",
      confirm_password: "",
      role: "attendee",
    },
  });

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/events");
    }
  }, [status, router]);

  async function onSubmit(values: RegisterValues) {
    setFormError(null);

    try {
      await registerRequest({
        full_name: values.full_name,
        email: values.email,
        password: values.password,
        role: values.role,
      });

      const auth = await loginRequest({
        email: values.email,
        password: values.password,
      });

      login(auth);
      toast.success("Account created");
      router.replace("/events");
    } catch (error) {
      setFormError(
        error instanceof ApiError
          ? error.message
          : "Could not create your account. Please try again.",
      );
    }
  }

  return (
    <form
      noValidate
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-5"
      aria-describedby={formError ? "register-error" : undefined}
    >
      {formError ? (
        <Alert variant="destructive" id="register-error">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      ) : null}

      <div className="space-y-2">
        <Label htmlFor="full_name">Full name</Label>
        <Input
          id="full_name"
          autoComplete="name"
          placeholder="Jane Doe"
          aria-invalid={Boolean(errors.full_name)}
          aria-describedby={errors.full_name ? "name-error" : undefined}
          {...register("full_name")}
        />
        {errors.full_name ? (
          <p id="name-error" className="text-xs text-destructive">
            {errors.full_name.message}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          aria-invalid={Boolean(errors.email)}
          aria-describedby={errors.email ? "email-error" : undefined}
          {...register("email")}
        />
        {errors.email ? (
          <p id="email-error" className="text-xs text-destructive">
            {errors.email.message}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <PasswordInput
          id="password"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.password)}
          aria-describedby={errors.password ? "password-error" : "password-help"}
          {...register("password")}
        />
        {errors.password ? (
          <p id="password-error" className="text-xs text-destructive">
            {errors.password.message}
          </p>
        ) : (
          <p id="password-help" className="text-xs text-muted-foreground">
            8–128 characters.
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirm_password">Confirm password</Label>
        <PasswordInput
          id="confirm_password"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.confirm_password)}
          aria-describedby={
            errors.confirm_password ? "confirm-password-error" : undefined
          }
          {...register("confirm_password")}
        />
        {errors.confirm_password ? (
          <p id="confirm-password-error" className="text-xs text-destructive">
            {errors.confirm_password.message}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="role">Account type</Label>
        <Controller
          control={control}
          name="role"
          render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger id="role" aria-label="Account type">
                <SelectValue placeholder="Choose account type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="attendee">Attendee</SelectItem>
                <SelectItem value="organizer">Organizer</SelectItem>
              </SelectContent>
            </Select>
          )}
        />
        <p className="text-xs text-muted-foreground">
          Attendees book tickets. Organizers can publish events.
        </p>
      </div>

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Creating account…
          </>
        ) : (
          "Create account"
        )}
      </Button>
    </form>
  );
}
