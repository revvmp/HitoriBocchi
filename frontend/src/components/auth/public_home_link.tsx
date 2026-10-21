"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getSiteSettings } from "@/lib/api/auth";

export default function PublicHomeLink() {
  const [isPublic, setIsPublic] = useState(false);

  useEffect(() => {
    let isActive = true;

    getSiteSettings()
      .then((settings) => {
        if (isActive) {
          setIsPublic(!settings.login_required);
        }
      })
      .catch(() => undefined);

    return () => {
      isActive = false;
    };
  }, []);

  if (!isPublic) {
    return null;
  }

  return (
    <Link
      className="mt-3 flex h-10 w-full items-center justify-center rounded-lg border border-auth-border bg-auth-field px-4 text-sm font-semibold text-auth-text transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-auth-text/40"
      href="/"
    >
      Continue to Home
    </Link>
  );
}
