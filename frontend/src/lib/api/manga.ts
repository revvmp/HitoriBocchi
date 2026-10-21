import { requestWithSessionRefresh } from "@/lib/api/auth";
import {
  apiRequest,
  apiResponse,
  hasCsrfToken,
  readJsonLines,
} from "@/lib/api/client";
import type { Pagination } from "@/lib/api/anime";

export type MangaSummary = {
  id: number;
  title: string;
  title_english: string;
  synopsis: string;
  image: string;
  slug: string;
  rating: number;
  genres: string[];
  status: string;
  popularity: number | null;
  media_type: string;
  current_chapters: number;
  latest_chapter_number: string;
  total_chapters: number | string | null;
  updated_at: string;
  requires_import?: boolean;
};

export type MangaView =
  | "latest"
  | "bookmarks"
  | "ongoing"
  | "popular"
  | "hits";

export type MangaChapter = {
  id: number;
  manga_id: number;
  chapter_number: string;
  title: string;
  released_at: string | null;
  created_at: string;
};

export type MangaPage = {
  page: number;
  width: number | null;
  height: number | null;
  image_url: string;
};

type MangaListResponse = {
  mangas: MangaSummary[];
  pagination: Pagination;
};

type MangaDetailResponse = {
  manga: MangaSummary;
};

type MangaChaptersResponse = {
  count: number;
  chapters: MangaChapter[];
};

type MangaChapterPagesResponse = {
  manga: MangaSummary;
  chapter: MangaChapter;
  pages: MangaPage[];
  count: number;
};

type MangaImportResponse = {
  manga: MangaSummary;
};

type MangaBookmarkResponse = {
  is_bookmarked: boolean;
  message?: string;
};

export type MangaSearchEvent =
  | { type: "start"; total: number }
  | {
      type: "manga";
      manga: MangaSummary;
      replaces_skeleton: boolean;
    }
  | {
      type: "error";
      message: string;
      replaces_skeleton?: boolean;
    }
  | { type: "complete" };

const queries: Record<Exclude<MangaView, "bookmarks">, string> = {
  latest: "sort=latest",
  ongoing: "status=ongoing",
  popular: "sort=popularity",
  hits: "sort=rating",
};

function requestManga(
  view: MangaView,
  searchQuery: string | undefined,
  limit: number,
  offset: number,
) {
  if (view === "bookmarks") {
    return apiRequest<MangaListResponse>(
      `/api/manga/bookmarks?limit=${limit}&offset=${offset}`,
    );
  }

  const filter = searchQuery
    ? `search=${encodeURIComponent(searchQuery)}`
    : queries[view];

  return apiRequest<MangaListResponse>(
    `/api/manga?${filter}&limit=${limit}&offset=${offset}`,
  );
}

export function getManga(
  view: MangaView,
  searchQuery?: string,
  limit = 36,
  offset = 0,
) {
  return requestWithSessionRefresh(() =>
    requestManga(view, searchQuery, limit, offset),
  );
}

async function requestMangaSearch(
  searchQuery: string,
  limit: number,
  onEvent: (event: MangaSearchEvent) => void,
  signal?: AbortSignal,
) {
  const response = await apiResponse(
    `/api/manga/search-import?search=${encodeURIComponent(searchQuery)}&limit=${limit}`,
    { signal },
  );

  await readJsonLines(
    response,
    onEvent,
    "Unable to read manga search results",
  );
}

export function streamMangaSearch(
  searchQuery: string,
  limit: number,
  onEvent: (event: MangaSearchEvent) => void,
  signal?: AbortSignal,
) {
  return requestWithSessionRefresh(() =>
    requestMangaSearch(searchQuery, limit, onEvent, signal),
  );
}

function requestMangaImport(malId: number) {
  return apiRequest<MangaImportResponse>("/api/manga/import", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ mal_id: malId }),
    csrf: hasCsrfToken("access") ? "access" : undefined,
  });
}

export function importManga(malId: number) {
  return requestWithSessionRefresh(() =>
    requestMangaImport(malId),
  );
}

async function requestMangaDetails(slug: string) {
  const encodedSlug = encodeURIComponent(slug);
  const chaptersResponse = await apiRequest<MangaChaptersResponse>(
    `/api/manga/${encodedSlug}/chapters`,
  );
  const mangaResponse = await apiRequest<MangaDetailResponse>(
    `/api/manga/${encodedSlug}`,
  );

  return {
    manga: mangaResponse.manga,
    chapters: chaptersResponse.chapters,
  };
}

export function getMangaDetails(slug: string) {
  return requestWithSessionRefresh(() =>
    requestMangaDetails(slug),
  );
}

function requestMangaReader(slug: string, chapterNumber: string) {
  const encodedSlug = encodeURIComponent(slug);
  const encodedChapterNumber = encodeURIComponent(chapterNumber);

  return Promise.all([
    apiRequest<MangaChapterPagesResponse>(
      `/api/manga/${encodedSlug}/chapters/${encodedChapterNumber}/pages`,
    ),
    apiRequest<MangaChaptersResponse>(
      `/api/manga/${encodedSlug}/chapters`,
    ),
  ]).then(([reader, chapterList]) => ({
    ...reader,
    chapters: chapterList.chapters,
  }));
}

export function getMangaReader(
  slug: string,
  chapterNumber: string,
) {
  return requestWithSessionRefresh(() =>
    requestMangaReader(slug, chapterNumber),
  );
}

function requestMangaBookmark(slug: string) {
  return apiRequest<MangaBookmarkResponse>(
    `/api/manga/${encodeURIComponent(slug)}/bookmark`,
  );
}

export function getMangaBookmark(slug: string) {
  return requestWithSessionRefresh(() =>
    requestMangaBookmark(slug),
  );
}

function requestMangaBookmarkUpdate(slug: string, isBookmarked: boolean) {
  return apiRequest<MangaBookmarkResponse>(
    `/api/manga/${encodeURIComponent(slug)}/bookmark`,
    {
      method: isBookmarked ? "DELETE" : "POST",
      csrf: "access",
    },
  );
}

export function updateMangaBookmark(
  slug: string,
  isBookmarked: boolean,
) {
  return requestWithSessionRefresh(() =>
    requestMangaBookmarkUpdate(slug, isBookmarked),
  );
}
