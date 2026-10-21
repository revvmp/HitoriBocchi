"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import * as adminRoutes from "@/components/admin/admin_routes";

type FormStatus = {
  message: string;
  type: "error" | "success";
};

export type AdminAddCatalogFormConfig = {
  addItem: (malUrl: string) => Promise<{ message: string }>;
  description: string;
  errorMessage: string;
  headingId: string;
  inputId: string;
  inputLabel: string;
  placeholder: string;
  routes: adminRoutes.AdminRoutes;
  submitLabel: string;
  submittingLabel: string;
  title: string;
};

type AdminAddCatalogFormProps = {
  config: AdminAddCatalogFormConfig;
  onAdded: () => void;
};

// Adds an anime or manga from a MyAnimeList URL in the admin panel.
export default function AdminAddCatalogForm({
  config,
  onAdded,
}: AdminAddCatalogFormProps) {
  const router = useRouter();
  const [malUrl, setMalUrl] = useState("");
  const [status, setStatus] = useState<FormStatus | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedUrl = malUrl.trim();

    if (!normalizedUrl) {
      return;
    }

    setIsSubmitting(true);
    setStatus(null);

    try {
      const response = await config.addItem(normalizedUrl);

      setMalUrl("");
      setStatus({ message: response.message, type: "success" });
      onAdded();
    } catch (error) {
      if (adminRoutes.redirectOnAdminAuthorizationError(error, router, config.routes)) {
        return;
      }

      setStatus({
        message: error instanceof Error ? error.message : config.errorMessage,
        type: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section
      aria-labelledby={config.headingId}
      className="mb-8 rounded-lg border border-home-surface bg-home-surface/30 p-4 sm:p-5"
    >
      <h2 id={config.headingId} className="text-lg font-semibold sm:text-xl">
        {config.title}
      </h2>
      <p className="mt-1 text-sm text-home-muted">
        {config.description}
      </p>

      <form
        className="mt-4 flex flex-col gap-3 sm:flex-row"
        onSubmit={handleSubmit}
      >
        <label className="sr-only" htmlFor={config.inputId}>
          {config.inputLabel}
        </label>
        <input
          id={config.inputId}
          className="h-11 min-w-0 flex-1 rounded-md border border-home-surface bg-home-background px-3 text-sm text-home-text outline-none transition placeholder:text-home-muted focus:border-home-accent"
          disabled={isSubmitting}
          onChange={(event) => {
            setMalUrl(event.target.value);
            setStatus(null);
          }}
          placeholder={config.placeholder}
          required
          type="url"
          value={malUrl}
        />
        <button
          className="h-11 shrink-0 rounded-md bg-home-text px-5 text-sm font-semibold text-home-background transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting ? config.submittingLabel : config.submitLabel}
        </button>
      </form>

      <p
        aria-live="polite"
        className={`mt-2 min-h-5 text-sm ${
          status?.type === "success" ? "text-home-accent" : "text-home-muted"
        }`}
      >
        {status?.message}
      </p>
    </section>
  );
}
