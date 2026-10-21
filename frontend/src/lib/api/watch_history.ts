import { requestWithSessionRefresh } from "@/lib/api/auth";
import type { AnimeSummary } from "@/lib/api/anime";
import { apiRequest } from "@/lib/api/client";

export type WatchHistory = {
  user_id: number;
  episode_id: number;
  current_time_seconds: number;
  duration_seconds: number;
  last_watched_at: string;
  anime_title: string;
  episode_number: number;
  episode_title: string;
  anime_slug: string;
  anime_image: string;
  anime: AnimeSummary;
};

type WatchHistoryResponse = {
  watch_history: WatchHistory | null;
};

type WatchHistoryListResponse = {
  watch_history: WatchHistory[];
  pagination: {
    limit: number;
    offset: number;
    count: number;
    has_more: boolean;
  };
};

export type WatchHistorySettings = {
  tracking_enabled: boolean;
};

type SaveWatchHistoryOptions = {
  keepalive?: boolean;
};

export function getWatchHistory(limit = 36, offset = 0) {
  return requestWithSessionRefresh(() =>
    apiRequest<WatchHistoryListResponse>(
      "/api/watch-history?limit=" + limit + "&offset=" + offset,
    ),
  );
}

export function clearWatchHistory() {
  return requestWithSessionRefresh(() =>
    apiRequest<{ message: string }>("/api/watch-history", {
      method: "DELETE",
      csrf: "access",
    }),
  );
}

export function getWatchHistorySettings() {
  return requestWithSessionRefresh(() =>
    apiRequest<WatchHistorySettings>("/api/watch-history/settings"),
  );
}

export function updateWatchHistoryTracking(trackingEnabled: boolean) {
  return requestWithSessionRefresh(() =>
    apiRequest<WatchHistorySettings>("/api/watch-history/settings", {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ tracking_enabled: trackingEnabled }),
      csrf: "access",
    }),
  );
}

export function getEpisodeWatchHistory(
  slug: string,
  episodeNumber: number,
) {
  return requestWithSessionRefresh(() =>
    apiRequest<WatchHistoryResponse>(
      "/api/anime/" + encodeURIComponent(slug)
        + "/episodes/" + episodeNumber + "/watch-history",
    ),
  );
}

export function saveEpisodeWatchHistory(
  slug: string,
  episodeNumber: number,
  currentTimeSeconds: number,
  durationSeconds: number,
  options: SaveWatchHistoryOptions = {},
) {
  return requestWithSessionRefresh(() =>
    apiRequest<WatchHistoryResponse>(
      "/api/anime/" + encodeURIComponent(slug)
        + "/episodes/" + episodeNumber + "/watch-history",
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          current_time_seconds: currentTimeSeconds,
          duration_seconds: durationSeconds,
        }),
        csrf: "access",
        keepalive: options.keepalive,
      },
    ),
  );
}

export function deleteEpisodeWatchHistory(
  slug: string,
  episodeNumber: number,
) {
  return requestWithSessionRefresh(() =>
    apiRequest<{ message: string }>(
      "/api/anime/" + encodeURIComponent(slug)
        + "/episodes/" + episodeNumber + "/watch-history",
      {
        method: "DELETE",
        csrf: "access",
      },
    ),
  );
}
