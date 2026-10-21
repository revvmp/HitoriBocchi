"use client";

import { useCallback, useEffect, useState } from "react";

import {
  ADDITIONAL_EPISODE_STREAM_SERVERS,
  getAnidbEpisodeAvailability,
  getAnizoneEpisodeAvailability,
  getAdditionalEpisodeAvailability,
  getMiruroEpisodeAvailability,
  type EpisodeStreamAvailability,
} from "@/lib/api/episode";

type EpisodeStreamAvailabilityState = {
  episodeKey: string;
  providers: EpisodeStreamAvailability;
};

// Inventories are listed from lowest to highest precedence because a later
// inventory replaces an earlier one when both report the same provider.
const AVAILABILITY_SOURCES = [
  "additional",
  "miruro",
  "stream",
  "anizone",
  "anidb",
] as const;

type AvailabilitySource = (typeof AVAILABILITY_SOURCES)[number];

type AvailabilityBySource = Partial<
  Record<AvailabilitySource, EpisodeStreamAvailabilityState>
>;

// Each of these inventories loads independently and replaces its previous
// result; a failed request is recorded as an empty inventory for the episode.
const INDEPENDENT_INVENTORIES = [
  { request: getAnidbEpisodeAvailability, source: "anidb" },
  { request: getAnizoneEpisodeAvailability, source: "anizone" },
  { request: getMiruroEpisodeAvailability, source: "miruro" },
] as const;

function mergeEpisodeStreamAvailability(currentAvailability: EpisodeStreamAvailabilityState | undefined, episodeKey: string, providers: EpisodeStreamAvailability): EpisodeStreamAvailabilityState {
  return {
    episodeKey,
    providers: currentAvailability?.episodeKey === episodeKey
      ? { ...currentAvailability.providers, ...providers }
      : providers,
  };
}

export default function useEpisodeStreamAvailability(slug: string, episodeNumber: number, episodeKey: string, isValidEpisodeNumber: boolean) {
  const [availabilityBySource, setAvailabilityBySource] =
    useState<AvailabilityBySource>({});
  const hasStreamAvailability =
    availabilityBySource.stream?.episodeKey === episodeKey;
  const availableCategories: EpisodeStreamAvailability = {};

  for (const source of AVAILABILITY_SOURCES) {
    const availability = availabilityBySource[source];

    if (availability?.episodeKey === episodeKey) {
      Object.assign(availableCategories, availability.providers);
    }
  }

  const mergeSourceAvailability = useCallback(
    (
      source: AvailabilitySource,
      nextEpisodeKey: string,
      providers: EpisodeStreamAvailability,
    ) => {
      setAvailabilityBySource((currentAvailability) => ({
        ...currentAvailability,
        [source]: mergeEpisodeStreamAvailability(
          currentAvailability[source],
          nextEpisodeKey,
          providers,
        ),
      }));
    },
    [],
  );

  const mergeStreamAvailability = useCallback(
    (nextEpisodeKey: string, providers: EpisodeStreamAvailability) => {
      mergeSourceAvailability("stream", nextEpisodeKey, providers);
    },
    [mergeSourceAvailability],
  );

  useEffect(() => {
    let isActive = true;

    if (!isValidEpisodeNumber) {
      return;
    }

    const controller = new AbortController();

    for (const inventory of INDEPENDENT_INVENTORIES) {
      inventory.request(slug, episodeNumber)
        .then((response) => {
          if (isActive) {
            setAvailabilityBySource((currentAvailability) => ({
              ...currentAvailability,
              [inventory.source]: {
                episodeKey,
                providers: response.available_categories,
              },
            }));
          }
        })
        .catch(() => {
          if (isActive) {
            setAvailabilityBySource((currentAvailability) => ({
              ...currentAvailability,
              [inventory.source]: {
                episodeKey,
                providers: {},
              },
            }));
          }
        });
    }

    for (const server of ADDITIONAL_EPISODE_STREAM_SERVERS) {
      getAdditionalEpisodeAvailability(slug, episodeNumber, server.value, controller.signal)
        .then((response) => {
          if (!controller.signal.aborted) {
            mergeSourceAvailability(
              "additional",
              episodeKey,
              response.available_categories,
            );
          }
        })
        .catch(() => {
          // A failed independent provider must not interrupt current playback.
        });
    }

    return () => {
      isActive = false;
      controller.abort();
    };
  }, [
    episodeKey,
    episodeNumber,
    isValidEpisodeNumber,
    mergeSourceAvailability,
    slug,
  ]);

  return {
    availableCategories,
    hasStreamAvailability,
    mergeStreamAvailability,
  };
}
