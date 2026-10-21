"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { register } from "@/lib/api/auth";

const inputClassName =
  "h-10 w-full rounded-lg border border-auth-border bg-auth-field px-3 text-sm text-auth-text outline-none transition placeholder:text-auth-muted focus:border-auth-text focus:ring-2 focus:ring-auth-text/15 disabled:cursor-not-allowed disabled:opacity-60";

export default function RegisterForm() {
  const router = useRouter();
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);

    setErrorMessage("");
    setIsSubmitting(true);

    try {
      await register({
        username: formData.get("username")?.toString() ?? "",
        email: formData.get("email")?.toString() ?? "",
        password: formData.get("password")?.toString() ?? "",
        registrationKey:
          formData.get("registration_key")?.toString() ?? "",
      });

      router.replace("/login");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to register",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="space-y-3" onSubmit={handleSubmit}>
      <div className="space-y-1">
        <label
          className="block text-xs font-medium text-auth-text"
          htmlFor="username"
        >
          Username
        </label>
        <input
          id="username"
          name="username"
          type="text"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          required
          disabled={isSubmitting}
          placeholder="Enter your username"
          className={inputClassName}
        />
      </div>

      <div className="space-y-1">
        <label
          className="block text-xs font-medium text-auth-text"
          htmlFor="email"
        >
          Email
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          disabled={isSubmitting}
          placeholder="Enter your email"
          className={inputClassName}
        />
      </div>

      <div className="space-y-1">
        <label
          className="block text-xs font-medium text-auth-text"
          htmlFor="password"
        >
          Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          disabled={isSubmitting}
          placeholder="Enter your password"
          className={inputClassName}
        />
      </div>

      <div className="space-y-1">
        <label
          className="block text-xs font-medium text-auth-text"
          htmlFor="registration_key"
        >
          Registration key
        </label>
        <input
          id="registration_key"
          name="registration_key"
          type="password"
          autoComplete="off"
          required
          disabled={isSubmitting}
          placeholder="Enter the registration key"
          className={inputClassName}
        />
      </div>

      <div aria-live="polite" aria-atomic="true" className="min-h-4">
        {errorMessage && (
          <p className="text-xs leading-4 text-auth-text" role="alert">
            {errorMessage}
          </p>
        )}
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-auth-text bg-auth-text px-4 text-sm font-semibold text-auth-background shadow-md transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-auth-text/40 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting && (
          <span
            aria-hidden="true"
            className="size-4 animate-spin rounded-full border-2 border-auth-background/35 border-t-auth-background"
          />
        )}
        {isSubmitting ? "Creating account..." : "Register"}
      </button>
    </form>
  );
}
