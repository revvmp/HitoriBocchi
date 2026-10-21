import {
  requestWithSessionRefresh,
  type SiteSettings,
} from "@/lib/api/auth";
import type { AnimeSummary, Pagination } from "@/lib/api/anime";
import type { MangaSummary } from "@/lib/api/manga";
import { apiRequest } from "@/lib/api/client";

export type AdminUser = {
  id: number;
  username: string;
  email: string;
  episodes_completed: number;
  is_admin: number;
  created_at: string;
};

export type AdminUserUpdate = {
  username: string;
  email: string;
  isAdmin: boolean;
  password: string;
};

type AdminUsersResponse = {
  users: AdminUser[];
};

type AdminUserResponse = {
  message: string;
  user: AdminUser;
};

type AdminActionResponse = {
  message: string;
};

type AdminSiteSettingsResponse = AdminActionResponse & SiteSettings;

type AdminAnimeBulkDeleteResponse = AdminActionResponse & {
  deleted_count: number;
};

type AdminAnimePageResponse = {
  animes: AnimeSummary[];
  pagination: Pagination;
};

type AdminMangaPageResponse = {
  mangas: MangaSummary[];
  pagination: Pagination;
};

function requestLoginRequirementUpdate(loginRequired: boolean) {
  return apiRequest<AdminSiteSettingsResponse>("/api/admin/site-settings", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ login_required: loginRequired }),
    csrf: "access",
  });
}

export function updateLoginRequirement(loginRequired: boolean) {
  return requestWithSessionRefresh(() =>
    requestLoginRequirementUpdate(loginRequired),
  );
}

function requestAdminUsers() {
  return apiRequest<AdminUsersResponse>("/api/admin/users");
}

export function getAdminUsers() {
  return requestWithSessionRefresh(() =>
    requestAdminUsers(),
  );
}

function requestAdminUserUpdate(
  userId: number,
  update: AdminUserUpdate,
) {
  return apiRequest<AdminUserResponse>(`/api/admin/users/${userId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      username: update.username,
      email: update.email,
      is_admin: update.isAdmin,
      password: update.password,
    }),
    csrf: "access",
  });
}

export function updateAdminUser(
  userId: number,
  update: AdminUserUpdate,
) {
  return requestWithSessionRefresh(() =>
    requestAdminUserUpdate(userId, update),
  );
}

function requestAdminUserDelete(userId: number) {
  return apiRequest<AdminActionResponse>(`/api/admin/users/${userId}`, {
    method: "DELETE",
    csrf: "access",
  });
}

export function deleteAdminUser(userId: number) {
  return requestWithSessionRefresh(() =>
    requestAdminUserDelete(userId),
  );
}

function requestAdminAnimeAdd(malUrl: string) {
  const formData = new FormData();

  formData.set("mal_url", malUrl);

  return apiRequest<AdminActionResponse>("/api/admin/anime", {
    method: "POST",
    body: formData,
    csrf: "access",
  });
}

export function addAdminAnime(malUrl: string) {
  return requestWithSessionRefresh(() =>
    requestAdminAnimeAdd(malUrl),
  );
}

function requestAdminAnimes(
  limit: number,
  offset: number,
  searchQuery: string,
) {
  const filter = searchQuery
    ? `search=${encodeURIComponent(searchQuery)}`
    : "sort=title";

  return apiRequest<AdminAnimePageResponse>(
    `/api/admin/anime?${filter}&limit=${limit}&offset=${offset}`,
  );
}

export function getAdminAnimes(
  limit = 20,
  offset = 0,
  searchQuery = "",
) {
  return requestWithSessionRefresh(() =>
    requestAdminAnimes(limit, offset, searchQuery),
  );
}

function requestAdminAnimeDelete(slug: string) {
  return apiRequest<AdminActionResponse>(
    `/api/admin/anime/${encodeURIComponent(slug)}`,
    {
      method: "DELETE",
      csrf: "access",
    },
  );
}

export function deleteAdminAnime(slug: string) {
  return requestWithSessionRefresh(() =>
    requestAdminAnimeDelete(slug),
  );
}

function requestAdminAnimesWithoutEpisodesDelete() {
  return apiRequest<AdminAnimeBulkDeleteResponse>(
    "/api/admin/anime/without-episodes",
    {
      method: "DELETE",
      csrf: "access",
    },
  );
}

export function deleteAdminAnimesWithoutEpisodes() {
  return requestWithSessionRefresh(() =>
    requestAdminAnimesWithoutEpisodesDelete(),
  );
}

function requestAdminMangaAdd(malUrl: string) {
  const formData = new FormData();

  formData.set("mal_url", malUrl);

  return apiRequest<AdminActionResponse>("/api/admin/manga", {
    method: "POST",
    body: formData,
    csrf: "access",
  });
}

export function addAdminManga(malUrl: string) {
  return requestWithSessionRefresh(() =>
    requestAdminMangaAdd(malUrl),
  );
}

function requestAdminMangas(
  limit: number,
  offset: number,
  searchQuery: string,
) {
  const filter = searchQuery
    ? `search=${encodeURIComponent(searchQuery)}`
    : "sort=title";

  return apiRequest<AdminMangaPageResponse>(
    `/api/admin/manga?${filter}&limit=${limit}&offset=${offset}`,
  );
}

export function getAdminMangas(
  limit = 20,
  offset = 0,
  searchQuery = "",
) {
  return requestWithSessionRefresh(() =>
    requestAdminMangas(limit, offset, searchQuery),
  );
}

function requestAdminMangaDelete(slug: string) {
  return apiRequest<AdminActionResponse>(
    `/api/admin/manga/${encodeURIComponent(slug)}`,
    {
      method: "DELETE",
      csrf: "access",
    },
  );
}

export function deleteAdminManga(slug: string) {
  return requestWithSessionRefresh(() =>
    requestAdminMangaDelete(slug),
  );
}

function requestAdminMangasWithoutChaptersDelete() {
  return apiRequest<AdminAnimeBulkDeleteResponse>(
    "/api/admin/manga/without-chapters",
    {
      method: "DELETE",
      csrf: "access",
    },
  );
}

export function deleteAdminMangasWithoutChapters() {
  return requestWithSessionRefresh(() =>
    requestAdminMangasWithoutChaptersDelete(),
  );
}
