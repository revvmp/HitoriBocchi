"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import type { AnimeEpisode, AnimeSummary } from "@/lib/api/anime";
import { getOptionalCurrentUser } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { completeEpisode, getEpisodeDetails } from "@/lib/api/episode";
import {
  getEpisodeWatchHistory,
  getWatchHistorySettings,
  saveEpisodeWatchHistory,
} from "@/lib/api/watch_history";

export type EpisodeDetails = {
  anime: AnimeSummary;
  episode: AnimeEpisode;
  episodes: AnimeEpisode[];
};

function isAuthorizationError(error: unknown) {
  return error instanceof ApiError && [401, 403].includes(error.status);
}

// Loads the episode, the viewer's resume position, and the account-protected
// progress/completion callbacks for the current episode.
export default function useEpisodeWatchSession(slug: string, episodeNumber: number, isValidEpisodeNumber: boolean) {
  const router = useRouter();
  const [details, setDetails] = useState<EpisodeDetails | null>(null);
  const [resumeTimeSeconds, setResumeTimeSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingWatchHistory, setIsLoadingWatchHistory] = useState(true);
  const [canRecordEpisodeCompletion, setCanRecordEpisodeCompletion] =
    useState(false);
  const [canSaveWatchHistory, setCanSaveWatchHistory] = useState(false);

  useEffect(() => {
    let isActive = true;

    if (!isValidEpisodeNumber) {
      return;
    }

    getEpisodeDetails(slug, episodeNumber)
      .then((response) => {
        if (isActive) {
          setDetails(response);
        }
      })
      .catch((error) => {
        if (!isActive) {
          return;
        }

        if (isAuthorizationError(error)) {
          router.replace("/login");
          return;
        }

        setErrorMessage(
          error instanceof Error ? error.message : "Unable to load episode",
        );
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    getOptionalCurrentUser()
      .then(async (currentUser) => {
        if (!isActive || !currentUser) {
          return;
        }

        setCanRecordEpisodeCompletion(true);
        const settings = await getWatchHistorySettings();

        if (!isActive || !settings.tracking_enabled) {
          return;
        }

        setCanSaveWatchHistory(true);
        const response = await getEpisodeWatchHistory(slug, episodeNumber);

        if (isActive) {
          const history = response.watch_history;
          setResumeTimeSeconds(
            history && history.current_time_seconds < history.duration_seconds * 0.9
              ? history.current_time_seconds
              : 0,
          );
        }
      })
      .catch((error) => {
        if (isActive && isAuthorizationError(error)) {
          setCanRecordEpisodeCompletion(false);
          setCanSaveWatchHistory(false);
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoadingWatchHistory(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [episodeNumber, isValidEpisodeNumber, router, slug]);

  const handleWatchProgress = useCallback(
    (
      currentTimeSeconds: number,
      durationSeconds: number,
      keepalive: boolean,
    ) => {
      void saveEpisodeWatchHistory(
        slug,
        episodeNumber,
        currentTimeSeconds,
        durationSeconds,
        { keepalive },
      ).catch((error) => {
        if (isAuthorizationError(error)) {
          setCanSaveWatchHistory(false);
        }
      });
    },
    [episodeNumber, slug],
  );

  const handleEpisodeComplete = useCallback(
    (currentTimeSeconds: number, durationSeconds: number) => {
      void completeEpisode(
        slug,
        episodeNumber,
        currentTimeSeconds,
        durationSeconds,
      ).catch((error) => {
        if (isAuthorizationError(error)) {
          setCanRecordEpisodeCompletion(false);
        }
      });
    },
    [episodeNumber, slug],
  );

  return {
    details,
    errorMessage,
    isLoading,
    isLoadingWatchHistory,
    onComplete: canRecordEpisodeCompletion ? handleEpisodeComplete : undefined,
    onProgress: canSaveWatchHistory ? handleWatchProgress : undefined,
    resumeTimeSeconds,
    setResumeTimeSeconds,
  };
}
