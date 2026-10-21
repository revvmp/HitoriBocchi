"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import {
  getEpisodeStreamLink,
  getEpisodeStreamWithFallback,
  type EpisodeStreamAvailability,
  type EpisodeStreamCategory,
  type EpisodeStreamProvider,
  type EpisodeStreamQuality,
} from "@/lib/api/episode";

type UseEpisodeStreamOptions = {
  availableCategories: EpisodeStreamAvailability;
  episodeKey: string;
  episodeNumber: number;
  hasStreamAvailability: boolean;
  isValidEpisodeNumber: boolean;
  mergeStreamAvailability: (
    episodeKey: string,
    providers: EpisodeStreamAvailability,
  ) => void;
  setResumeTimeSeconds: (currentTimeSeconds: number) => void;
  slug: string;
};

function getStreamSelectionKey(episodeKey: string, provider: EpisodeStreamProvider, category: EpisodeStreamCategory) {
  return `${episodeKey}:${provider}:${category}`;
}

// Once the episode inventory is known, request the selected provider directly;
// before that, try each known provider in order until one returns a stream.
function requestEpisodeStream(slug: string, episodeNumber: number, provider: EpisodeStreamProvider, category: EpisodeStreamCategory, hasStreamAvailability: boolean, signal?: AbortSignal) {
  return hasStreamAvailability
    ? getEpisodeStreamLink(
        slug,
        episodeNumber,
        undefined,
        provider,
        category,
        signal,
      ).then((response) => ({
        ...response,
        provider,
      }))
    : getEpisodeStreamWithFallback(
        slug,
        episodeNumber,
        undefined,
        provider,
        category,
        signal,
      );
}

export default function useEpisodeStream({
  availableCategories,
  episodeKey,
  episodeNumber,
  hasStreamAvailability,
  isValidEpisodeNumber,
  mergeStreamAvailability,
  setResumeTimeSeconds,
  slug,
}: UseEpisodeStreamOptions) {
  const router = useRouter();
  const playbackTimeRef = useRef(0);
  const loadedStreamSelectionRef = useRef("");
  const [streamUrl, setStreamUrl] = useState("");
  const [subtitleUrl, setSubtitleUrl] = useState("");
  const [selectedCategory, setSelectedCategory] =
    useState<EpisodeStreamCategory>("sub");
  const [selectedProvider, setSelectedProvider] =
    useState<EpisodeStreamProvider>("anizone");
  const [selectedQuality, setSelectedQuality] =
    useState<EpisodeStreamQuality>("1080p");
  const [streamErrorMessage, setStreamErrorMessage] = useState("");
  const [isLoadingStream, setIsLoadingStream] = useState(true);

  useEffect(() => {
    let isActive = true;
    let isFallingBackToSub = false;

    if (!isValidEpisodeNumber) {
      return;
    }

    const streamSelectionKey = getStreamSelectionKey(
      episodeKey,
      selectedProvider,
      selectedCategory,
    );

    // Availability updates must not replace an already resolved signed stream.
    if (loadedStreamSelectionRef.current === streamSelectionKey) {
      return;
    }

    const controller = new AbortController();

    requestEpisodeStream(
      slug,
      episodeNumber,
      selectedProvider,
      selectedCategory,
      hasStreamAvailability,
      controller.signal,
    )
      .then((response) => {
        if (isActive) {
          loadedStreamSelectionRef.current = getStreamSelectionKey(
            episodeKey,
            response.provider,
            selectedCategory,
          );
          mergeStreamAvailability(episodeKey, response.available_categories);
          setSelectedProvider(response.provider);
          setSelectedQuality(response.quality ?? "1080p");
          setStreamUrl(response.stream_url);
          setSubtitleUrl(response.subtitle_url ?? "");
        }
      })
      .catch((error) => {
        if (!isActive) {
          return;
        }

        if (
          error instanceof ApiError &&
          [401, 403].includes(error.status)
        ) {
          router.replace("/login");
          return;
        }

        if (
          selectedCategory === "dub" &&
          (
            !hasStreamAvailability ||
            (
              error instanceof ApiError &&
              error.status === 404
            )
          )
        ) {
          isFallingBackToSub = true;
          setSelectedCategory("sub");
          return;
        }

        setStreamErrorMessage(
          error instanceof Error ? error.message : "Unable to load stream",
        );
      })
      .finally(() => {
        if (isActive && !isFallingBackToSub) {
          setIsLoadingStream(false);
        }
      });

    return () => {
      isActive = false;
      controller.abort();
    };
  }, [
    episodeKey,
    episodeNumber,
    hasStreamAvailability,
    isValidEpisodeNumber,
    mergeStreamAvailability,
    router,
    selectedCategory,
    selectedProvider,
    slug,
  ]);

  const handleQualityChange = useCallback(
    (quality: EpisodeStreamQuality, currentTimeSeconds: number) => {
      setStreamErrorMessage("");

      void getEpisodeStreamLink(
        slug,
        episodeNumber,
        quality,
        selectedProvider,
        selectedCategory,
      )
        .then((response) => {
          mergeStreamAvailability(episodeKey, response.available_categories);
          setResumeTimeSeconds(currentTimeSeconds);
          setSelectedQuality(response.quality ?? quality);
          setStreamUrl(response.stream_url);
          setSubtitleUrl(response.subtitle_url ?? "");
        })
        .catch((error) => {
          setStreamErrorMessage(
            error instanceof Error ? error.message : "Unable to load stream",
          );
        });
    },
    [
      episodeKey,
      episodeNumber,
      mergeStreamAvailability,
      selectedCategory,
      selectedProvider,
      setResumeTimeSeconds,
      slug,
    ],
  );

  const handlePlaybackTimeChange = useCallback(
    (currentTimeSeconds: number) => {
      playbackTimeRef.current = currentTimeSeconds;
    },
    [],
  );

  // Server and version changes resume from the current playback position.
  function resetStreamForNewSelection() {
    setResumeTimeSeconds(playbackTimeRef.current);
    setIsLoadingStream(true);
    setStreamErrorMessage("");
    setStreamUrl("");
    setSubtitleUrl("");
    loadedStreamSelectionRef.current = "";
  }

  function handleCategoryChange(category: EpisodeStreamCategory) {
    if (category === selectedCategory) {
      return;
    }

    resetStreamForNewSelection();
    setSelectedCategory(category);
  }

  function handleServerChange(provider: EpisodeStreamProvider) {
    if (provider === selectedProvider) {
      return;
    }

    const providerCategories = availableCategories[provider] ?? [];

    resetStreamForNewSelection();
    setSelectedCategory(
      providerCategories.includes(selectedCategory)
        ? selectedCategory
        : providerCategories[0] ?? "sub",
    );
    setSelectedProvider(provider);
  }

  async function handleRetryStream() {
    setIsLoadingStream(true);
    setStreamErrorMessage("");
    loadedStreamSelectionRef.current = "";

    try {
      const response = await requestEpisodeStream(
        slug,
        episodeNumber,
        selectedProvider,
        selectedCategory,
        hasStreamAvailability,
      );
      loadedStreamSelectionRef.current = getStreamSelectionKey(
        episodeKey,
        response.provider,
        selectedCategory,
      );
      mergeStreamAvailability(episodeKey, response.available_categories);
      setSelectedProvider(response.provider);
      setStreamUrl(response.stream_url);
      setSubtitleUrl(response.subtitle_url ?? "");
    } catch (error) {
      setStreamErrorMessage(
        error instanceof Error ? error.message : "Unable to load stream",
      );
    } finally {
      setIsLoadingStream(false);
    }
  }

  return {
    handleCategoryChange,
    handlePlaybackTimeChange,
    handleQualityChange,
    handleRetryStream,
    handleServerChange,
    isLoadingStream,
    selectedCategory,
    selectedProvider,
    selectedQuality,
    streamErrorMessage,
    streamUrl,
    subtitleUrl,
  };
}
