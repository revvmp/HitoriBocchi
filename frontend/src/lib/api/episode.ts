import { requestWithSessionRefresh } from "@/lib/api/auth";
import type { AnimeEpisode, AnimeSummary } from "@/lib/api/anime";
import { apiRequest, ApiError } from "@/lib/api/client";

type AnimeDetailResponse = {
  anime: AnimeSummary;
};

type AnimeEpisodeResponse = {
  episode: AnimeEpisode;
};

type AnimeEpisodesResponse = {
  episodes: AnimeEpisode[];
};

type EpisodeStreamResponse = {
  anime_id: number;
  available_categories: EpisodeStreamAvailability;
  category: EpisodeStreamCategory;
  episode_number: number;
  stream_url: string;
  subtitle_url: string | null;
  quality?: EpisodeStreamQuality | null;
};

type EpisodeStreamAvailabilityResponse = {
  anime_id: number;
  available_categories: EpisodeStreamAvailability;
  episode_number: number;
};

export const EPISODE_STREAM_CATEGORIES = [
  { label: "Sub", value: "sub" },
  { label: "Dub", value: "dub" },
] as const;
export const EPISODE_STREAM_QUALITIES = ["1080p", "720p", "360p"] as const;
export const ADDITIONAL_EPISODE_STREAM_SERVERS = [
  { label: "Re:Anime", value: "reanime" },
  { label: "Anibd.app", value: "anibd" },
  { label: "AniNeko", value: "anineko" },
  { label: "Anikoto", value: "anikoto" },
] as const;
export const EPISODE_STREAM_SERVERS = [
  { label: "anizone", value: "anizone" },
  { label: "anidb", value: "anidb" },
  { label: "AnimePahe", value: "animepahe" },
  { label: "KickAssAnime", value: "kickassanime" },
  { label: "AniWaves", value: "aniwaves" },
  ...ADDITIONAL_EPISODE_STREAM_SERVERS,
] as const;
const AUTOMATIC_STREAM_PROVIDER_TIMEOUT_MS = 8_000;

export type EpisodeStreamCategory =
  (typeof EPISODE_STREAM_CATEGORIES)[number]["value"];
export type EpisodeStreamQuality =
  (typeof EPISODE_STREAM_QUALITIES)[number];
export type EpisodeStreamProvider =
  (typeof EPISODE_STREAM_SERVERS)[number]["value"];
export type EpisodeStreamAvailability = Partial<
  Record<EpisodeStreamProvider, EpisodeStreamCategory[]>
>;

export type EpisodeSkipTime = {
  skip_type: "opening" | "ending";
  start_time: number;
  end_time: number;
};

type EpisodeSkipTimesResponse = {
  anime_id: number;
  episode_number: number;
  skip_times: EpisodeSkipTime[];
};

type EpisodeCompletionResponse = {
  episodes_completed: number;
  message: string;
};

function requestEpisodeDetails(slug: string, episodeNumber: number) {
  const encodedSlug = encodeURIComponent(slug);

  return Promise.all([
    apiRequest<AnimeDetailResponse>(`/api/anime/${encodedSlug}`),
    apiRequest<AnimeEpisodeResponse>(
      `/api/anime/${encodedSlug}/episodes/${episodeNumber}`,
    ),
    apiRequest<AnimeEpisodesResponse>(
      `/api/anime/${encodedSlug}/episodes`,
    ),
  ]).then(([animeResponse, episodeResponse, episodesResponse]) => ({
    anime: animeResponse.anime,
    episode: episodeResponse.episode,
    episodes: episodesResponse.episodes,
  }));
}

export function getEpisodeDetails(slug: string, episodeNumber: number) {
  return requestWithSessionRefresh(() =>
    requestEpisodeDetails(slug, episodeNumber),
  );
}

function requestEpisodeStreamLink(
  slug: string,
  episodeNumber: number,
  quality?: EpisodeStreamQuality,
  provider: EpisodeStreamProvider = "anizone",
  category: EpisodeStreamCategory = "sub",
  signal?: AbortSignal,
) {
  const searchParams = new URLSearchParams({ category, provider });

  if (quality) {
    searchParams.set("quality", quality);
  }

  return apiRequest<EpisodeStreamResponse>(
    `/api/anime/${encodeURIComponent(slug)}/episodes/${episodeNumber}/stream?${searchParams.toString()}`,
    { signal },
  );
}

type AdditionalEpisodeStreamProvider =
  (typeof ADDITIONAL_EPISODE_STREAM_SERVERS)[number]["value"];

function requestEpisodeAvailability(
  slug: string,
  episodeNumber: number,
  inventoryPath: string,
  signal?: AbortSignal,
) {
  return apiRequest<EpisodeStreamAvailabilityResponse>(
    `/api/anime/${encodeURIComponent(slug)}/episodes/${episodeNumber}/${inventoryPath}/availability`,
    { signal },
  );
}

async function requestAvailabilityWithRetry(request: () => Promise<EpisodeStreamAvailabilityResponse>, signal?: AbortSignal) {
  try {
    return await requestWithSessionRefresh(request);
  } catch (error) {
    if (signal?.aborted || (error instanceof Error && error.name === "AbortError") || (error instanceof ApiError && error.status < 500)) {
      throw error;
    }

    // A transient inventory failure must not hide a server for the whole visit.
    return requestWithSessionRefresh(request);
  }
}

export function getAnidbEpisodeAvailability(slug: string, episodeNumber: number) {
  return requestAvailabilityWithRetry(() =>
    requestEpisodeAvailability(slug, episodeNumber, "anidb"),
  );
}

export function getAnizoneEpisodeAvailability(slug: string, episodeNumber: number) {
  return requestAvailabilityWithRetry(() =>
    requestEpisodeAvailability(slug, episodeNumber, "anizone"),
  );
}

export function getMiruroEpisodeAvailability(slug: string, episodeNumber: number) {
  return requestAvailabilityWithRetry(() =>
    requestEpisodeAvailability(slug, episodeNumber, "miruro"),
  );
}

export function getAdditionalEpisodeAvailability(slug: string, episodeNumber: number, provider: AdditionalEpisodeStreamProvider, signal?: AbortSignal) {
  return requestAvailabilityWithRetry(() =>
    requestEpisodeAvailability(slug, episodeNumber, `playback/${provider}`, signal), signal,
  );
}

export function getEpisodeStreamLink(
  slug: string,
  episodeNumber: number,
  quality?: EpisodeStreamQuality,
  provider: EpisodeStreamProvider = "anizone",
  category: EpisodeStreamCategory = "sub",
  signal?: AbortSignal,
) {
  return requestWithSessionRefresh(() =>
    requestEpisodeStreamLink(
      slug,
      episodeNumber,
      quality,
      provider,
      category,
      signal,
    ),
  );
}

export async function getEpisodeStreamWithFallback(
  slug: string,
  episodeNumber: number,
  quality?: EpisodeStreamQuality,
  preferredProvider: EpisodeStreamProvider = "anizone",
  category: EpisodeStreamCategory = "sub",
  signal?: AbortSignal,
): Promise<EpisodeStreamResponse & { provider: EpisodeStreamProvider }> {
  const providers = [
    preferredProvider,
    ...EPISODE_STREAM_SERVERS
      .map((server) => server.value)
      .filter((provider) => provider !== preferredProvider),
  ];
  let lastError: unknown = new Error(
    "No streaming server is available for this episode",
  );

  for (const provider of providers) {
    const controller = new AbortController();
    let didTimeOut = false;
    const abortProviderRequest = () => controller.abort();
    const timeoutId = setTimeout(() => {
      didTimeOut = true;
      controller.abort();
    }, AUTOMATIC_STREAM_PROVIDER_TIMEOUT_MS);

    signal?.addEventListener("abort", abortProviderRequest, { once: true });

    if (signal?.aborted) {
      controller.abort();
    }

    try {
      const response = await getEpisodeStreamLink(
        slug,
        episodeNumber,
        quality,
        provider,
        category,
        controller.signal,
      );

      return {
        ...response,
        provider,
      };
    } catch (error) {
      if (signal?.aborted) {
        throw error;
      }

      if (
        error instanceof ApiError &&
        [401, 403].includes(error.status)
      ) {
        throw error;
      }

      lastError = didTimeOut
        ? new Error(`${provider} did not respond in time`)
        : error;
    } finally {
      clearTimeout(timeoutId);
      signal?.removeEventListener("abort", abortProviderRequest);
    }
  }

  throw lastError;
}

function requestEpisodeSkipTimes(
  slug: string,
  episodeNumber: number,
  episodeLength: number,
) {
  return apiRequest<EpisodeSkipTimesResponse>(
    `/api/anime/${encodeURIComponent(slug)}/episodes/${episodeNumber}/skip-times?episode_length=${episodeLength.toFixed(3)}`,
  );
}

export function getEpisodeSkipTimes(
  slug: string,
  episodeNumber: number,
  episodeLength: number,
) {
  return requestWithSessionRefresh(() =>
    requestEpisodeSkipTimes(slug, episodeNumber, episodeLength),
  );
}

function requestEpisodeCompletion(
  slug: string,
  episodeNumber: number,
  currentTimeSeconds: number,
  durationSeconds: number,
) {
  return apiRequest<EpisodeCompletionResponse>(
    "/api/anime/" + encodeURIComponent(slug)
      + "/episodes/" + episodeNumber + "/completion",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        current_time_seconds: currentTimeSeconds,
        duration_seconds: durationSeconds,
      }),
      csrf: "access",
    },
  );
}

export function completeEpisode(
  slug: string,
  episodeNumber: number,
  currentTimeSeconds: number,
  durationSeconds: number,
) {
  return requestWithSessionRefresh(() =>
    requestEpisodeCompletion(
      slug,
      episodeNumber,
      currentTimeSeconds,
      durationSeconds,
    ),
  );
}
