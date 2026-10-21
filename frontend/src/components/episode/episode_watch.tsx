"use client";

import Link from "next/link";

import EpisodeComments from "@/components/episode/episode_comments";
import EpisodeNavigation from "@/components/episode/episode_navigation";
import EpisodeStreamSelectors from "@/components/episode/episode_stream_selectors";
import useEpisodeStream from "@/components/episode/use_episode_stream";
import useEpisodeStreamAvailability from "@/components/episode/use_episode_stream_availability";
import useEpisodeWatchSession from "@/components/episode/use_episode_watch_session";
import VideoPlayer from "@/components/player/video_player";
import { EPISODE_STREAM_SERVERS } from "@/lib/api/episode";

type EpisodeWatchProps = {
  slug: string;
  episodeNumber: number;
};

const pageClassName =
  "min-h-svh bg-home-background px-4 pt-5 pb-28 text-home-text sm:px-6 sm:pt-7 sm:pb-36 lg:px-8";

function EpisodePageMessage({ message, slug }: { message: string; slug: string }) {
  return (
    <main className={pageClassName}>
      <div className="mx-auto max-w-6xl">
        <p className="text-sm text-home-muted">{message}</p>
        <Link
          className="mt-4 inline-block text-sm font-semibold text-home-accent"
          href={`/anime/${slug}`}
        >
          Return to anime
        </Link>
      </div>
    </main>
  );
}

export default function EpisodeWatch({
  slug,
  episodeNumber,
}: EpisodeWatchProps) {
  const episodeKey = `${slug}:${episodeNumber}`;
  const isValidEpisodeNumber =
    Number.isInteger(episodeNumber) && episodeNumber > 0;
  const session = useEpisodeWatchSession(
    slug,
    episodeNumber,
    isValidEpisodeNumber,
  );
  const availability = useEpisodeStreamAvailability(
    slug,
    episodeNumber,
    episodeKey,
    isValidEpisodeNumber,
  );
  const stream = useEpisodeStream({
    availableCategories: availability.availableCategories,
    episodeKey,
    episodeNumber,
    hasStreamAvailability: availability.hasStreamAvailability,
    isValidEpisodeNumber,
    mergeStreamAvailability: availability.mergeStreamAvailability,
    setResumeTimeSeconds: session.setResumeTimeSeconds,
    slug,
  });
  const { availableCategories } = availability;
  const { details } = session;

  if (!isValidEpisodeNumber) {
    return (
      <EpisodePageMessage
        message="Episode number must be a positive whole number."
        slug={slug}
      />
    );
  }

  if (session.isLoading) {
    return (
      <main className={pageClassName}>
        <div className="mx-auto max-w-6xl animate-pulse">
          <div className="h-5 w-36 rounded bg-home-surface" />
          <div className="mt-4 h-8 w-3/5 rounded bg-home-surface" />
          <div className="mt-5 aspect-video rounded-lg bg-home-surface" />
        </div>
      </main>
    );
  }

  if (session.errorMessage || !details) {
    return (
      <EpisodePageMessage
        message={session.errorMessage || "Episode not found."}
        slug={slug}
      />
    );
  }

  const animeTitle = details.anime.title_english || details.anime.title;
  const episodeTitle =
    details.episode.title || `Episode ${details.episode.episode_number}`;
  const sortedEpisodes = [...details.episodes].sort(
    (firstEpisode, secondEpisode) =>
      firstEpisode.episode_number - secondEpisode.episode_number,
  );
  const previousEpisode = sortedEpisodes
    .filter((episode) => episode.episode_number < episodeNumber)
    .at(-1);
  const nextEpisode = sortedEpisodes.find(
    (episode) => episode.episode_number > episodeNumber,
  );
  const selectedProviderCategories =
    availableCategories[stream.selectedProvider] ?? ["sub"];
  // Only list providers that store this episode, plus the current selection.
  const visibleServers = EPISODE_STREAM_SERVERS.filter(
    (server) =>
      server.value === stream.selectedProvider
      || (availableCategories[server.value]?.length ?? 0) > 0,
  );

  return (
    <main className={pageClassName}>
      <div className="mx-auto max-w-6xl">
        <Link
          className="inline-flex items-center gap-2 text-sm font-semibold text-home-accent hover:text-home-text"
          href={`/anime/${details.anime.slug}`}
        >
          <span aria-hidden="true">&larr;</span>
          View anime page
        </Link>

        <header className="mt-4">
          <p className="text-sm font-semibold uppercase tracking-wide text-home-accent">
            Episode {details.episode.episode_number}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
            {animeTitle}
          </h1>
          <p className="mt-1 text-base text-home-muted">{episodeTitle}</p>
        </header>

        <section className="mt-5" aria-label="Episode player">
          <div className="flex aspect-video items-center justify-center overflow-hidden rounded-lg border border-home-surface bg-home-surface/40">
            {stream.isLoadingStream || session.isLoadingWatchHistory ? (
              <p className="text-sm text-home-muted">Loading stream...</p>
            ) : stream.streamUrl ? (
              <VideoPlayer
                episodeNumber={details.episode.episode_number}
                initialTimeSeconds={session.resumeTimeSeconds}
                onComplete={session.onComplete}
                onProgress={session.onProgress}
                onQualityChange={stream.handleQualityChange}
                onTimeChange={stream.handlePlaybackTimeChange}
                quality={stream.selectedQuality}
                slug={details.anime.slug}
                src={stream.streamUrl}
                subtitleSrc={stream.subtitleUrl || undefined}
              />
            ) : (
              <div className="px-5 text-center">
                <p className="text-sm text-home-muted">
                  {stream.streamErrorMessage || "The stream is currently unavailable."}
                </p>
                <button
                  className="mt-4 rounded-md bg-home-accent px-4 py-2 text-sm font-semibold text-home-background transition hover:opacity-90"
                  type="button"
                  onClick={stream.handleRetryStream}
                >
                  Retry stream
                </button>
              </div>
            )}
          </div>
          <EpisodeStreamSelectors
            categories={selectedProviderCategories}
            isLoadingStream={stream.isLoadingStream}
            onCategoryChange={stream.handleCategoryChange}
            onServerChange={stream.handleServerChange}
            selectedCategory={stream.selectedCategory}
            selectedProvider={stream.selectedProvider}
            servers={visibleServers}
          />
        </section>

        <EpisodeNavigation
          animeSlug={details.anime.slug}
          nextEpisode={nextEpisode}
          previousEpisode={previousEpisode}
        />

        <EpisodeComments
          episodeNumber={details.episode.episode_number}
          slug={details.anime.slug}
        />
      </div>
    </main>
  );
}
