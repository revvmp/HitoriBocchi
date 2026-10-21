"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { updateLoginRequirement } from "@/lib/api/admin";
import { getSiteSettings } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";

export default function AdminLoginSetting() {
  const router = useRouter();
  const [loginRequired, setLoginRequired] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isActive = true;

    getSiteSettings()
      .then((settings) => {
        if (isActive) {
          setLoginRequired(settings.login_required);
        }
      })
      .catch((error) => {
        if (isActive) {
          setErrorMessage(
            error instanceof Error
              ? error.message
              : "Unable to load login setting",
          );
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  async function handleToggle() {
    const nextLoginRequired = !loginRequired;
    setIsSaving(true);
    setErrorMessage("");

    try {
      const settings = await updateLoginRequirement(nextLoginRequired);
      setLoginRequired(settings.login_required);
    } catch (error) {
      if (error instanceof ApiError && [401, 403].includes(error.status)) {
        router.replace("/login?next=/admin");
        return;
      }

      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Unable to update login setting",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="mb-8 rounded-lg border border-home-surface bg-home-surface/30 p-4 sm:flex sm:items-center sm:justify-between sm:gap-6 sm:p-5">
      <div>
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">Login Requirement</h2>
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
              loginRequired
                ? "bg-home-accent text-home-background"
                : "bg-home-surface text-home-muted"
            }`}
          >
            {loginRequired ? "On" : "Off"}
          </span>
        </div>
        <p className="mt-1 text-sm text-home-muted">
          {loginRequired
            ? "Users must sign in before browsing or watching anime."
            : "The catalog and episode playback are open without an account."}
        </p>
        {errorMessage && (
          <p className="mt-2 text-sm text-home-text" role="alert">
            {errorMessage}
          </p>
        )}
      </div>

      <button
        aria-checked={loginRequired}
        className="mt-4 min-w-28 rounded-md border border-home-accent/60 px-4 py-2.5 text-sm font-semibold text-home-text transition hover:border-home-accent hover:bg-home-surface disabled:cursor-not-allowed disabled:opacity-60 sm:mt-0"
        disabled={isLoading || isSaving}
        onClick={handleToggle}
        role="switch"
        type="button"
      >
        {isLoading
          ? "Loading..."
          : isSaving
            ? "Saving..."
            : "Turn " + (loginRequired ? "off" : "on")}
      </button>
    </section>
  );
}
