import { requestWithSessionRefresh } from "@/lib/api/auth";
import {
  apiRequest,
  apiResponse,
  hasCsrfToken,
  readJsonLines,
} from "@/lib/api/client";

export type AnimeSummary = {
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
  current_episodes: number;
  latest_episode_number: number;
  total_episodes: number | string | null;
  updated_at: string;
  requires_import?: boolean;
};

export type AnimeView = "latest" | "ongoing" | "popular" | "hits";

export type AnimeEpisode = {
  id: number;
  anime_id: number;
  episode_number: number;
  provider_episode_id: string;
  title: string;
  created_at: string;
};

export type Pagination = {
  count: number;
  has_more: boolean;
  limit: number;
  offset: number;
};

type AnimeListResponse = {
  animes: AnimeSummary[];
  pagination: Pagination;
};

type AnimeDetailResponse = {
  anime: AnimeSummary;
};

type AnimeEpisodesResponse = {
  count: number;
  episodes: AnimeEpisode[];
};

type AnimeImportResponse = {
  anime: AnimeSummary;
};

export type AnimeSearchEvent =
  | { type: "start"; total: number }
  | {
      type: "anime";
      anime: AnimeSummary;
      replaces_skeleton: boolean;
    }
  | {
      type: "error";
      message: string;
      replaces_skeleton?: boolean;
    }
  | { type: "complete" };

const queries: Record<AnimeView, string> = {
  latest: "sort=latest",
  ongoing: "status=ongoing",
  popular: "sort=popularity",
  hits: "sort=rating",
};

function requestAnime(
  view: AnimeView,
  searchQuery: string | undefined,
  limit: number,
  offset: number,
) {
  const filter = searchQuery
    ? `search=${encodeURIComponent(searchQuery)}`
    : queries[view];

  return apiRequest<AnimeListResponse>(
    `/api/anime?${filter}&limit=${limit}&offset=${offset}`,
  );
}

export function getAnime(
  view: AnimeView,
  searchQuery?: string,
  limit = 36,
  offset = 0,
) {
  return requestWithSessionRefresh(() =>
    requestAnime(view, searchQuery, limit, offset),
  );
}

async function requestAnimeSearch(
  searchQuery: string,
  limit: number,
  onEvent: (event: AnimeSearchEvent) => void,
  signal?: AbortSignal,
) {
  const response = await apiResponse(
    `/api/anime/search-import?search=${encodeURIComponent(searchQuery)}&limit=${limit}`,
    { signal },
  );

  await readJsonLines(
    response,
    onEvent,
    "Unable to read anime search results",
  );
}

export function streamAnimeSearch(
  searchQuery: string,
  limit: number,
  onEvent: (event: AnimeSearchEvent) => void,
  signal?: AbortSignal,
) {
  return requestWithSessionRefresh(() =>
    requestAnimeSearch(searchQuery, limit, onEvent, signal),
  );
}

function requestAnimeImport(malId: number) {
  return apiRequest<AnimeImportResponse>("/api/anime/import", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ mal_id: malId }),
    csrf: hasCsrfToken("access") ? "access" : undefined,
  });
}

export function importAnime(malId: number) {
  return requestWithSessionRefresh(() =>
    requestAnimeImport(malId),
  );
}

async function requestAnimeDetails(slug: string) {
  const encodedSlug = encodeURIComponent(slug);
  const episodesResponse = await apiRequest<AnimeEpisodesResponse>(
    `/api/anime/${encodedSlug}/episodes`,
  );
  const animeResponse = await apiRequest<AnimeDetailResponse>(
    `/api/anime/${encodedSlug}`,
  );

  return {
    anime: animeResponse.anime,
    episodes: episodesResponse.episodes,
  };
}

export function getAnimeDetails(slug: string) {
  return requestWithSessionRefresh(() =>
    requestAnimeDetails(slug),
  );
}
