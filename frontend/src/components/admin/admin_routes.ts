import type { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api/client";

export type AdminRoutes = {
  forbiddenPath: string;
  loginPath: string;
};

export const ANIME_ADMIN_ROUTES: AdminRoutes = {
  forbiddenPath: "/",
  loginPath: "/login?next=/admin",
};

export const MANGA_ADMIN_ROUTES: AdminRoutes = {
  forbiddenPath: "/manga",
  loginPath: "/login?next=/manga/admin",
};

// Signed-out admins return to login and non-admins leave the admin page.
// Returns true when the error was an authorization failure that redirected.
export function redirectOnAdminAuthorizationError(error: unknown, router: ReturnType<typeof useRouter>, routes: AdminRoutes) {
  if (error instanceof ApiError && error.status === 401) {
    router.replace(routes.loginPath);
    return true;
  }

  if (error instanceof ApiError && error.status === 403) {
    router.replace(routes.forbiddenPath);
    return true;
  }

  return false;
}
