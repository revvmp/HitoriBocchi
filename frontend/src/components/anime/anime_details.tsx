"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  getAnimeDetails,
  type AnimeEpisode,
  type AnimeSummary,
} from "@/lib/api/anime";
import { ApiError } from "@/lib/api/client";

type AnimeDetailsProps = {
  slug: string;
};

export default function AnimeDetails({ slug }: AnimeDetailsProps) {
  const router = useRouter();
  const [anime, setAnime] = useState<AnimeSummary | null>(null);
  const [episodes, setEpisodes] = useState<AnimeEpisode[]>([]);
  const [episodeQuery, setEpisodeQuery] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isActive = true;

    getAnimeDetails(slug)
      .then((response) => {
        if (!isActive) {
          return;
        }

        setAnime(response.anime);
        setEpisodes(response.episodes);
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

        setErrorMessage(
          error instanceof Error ? error.message : "Unable to load anime",
        );
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [router, slug]);

  const filteredEpisodes = useMemo(() => {
    const normalizedQuery = episodeQuery.trim().toLocaleLowerCase();

    if (!normalizedQuery) {
      return episodes;
    }

    return episodes.filter((episode) => (
      String(episode.episode_number).includes(normalizedQuery) ||
      episode.title.toLocaleLowerCase().includes(normalizedQuery)
    ));
  }, [episodeQuery, episodes]);

  if (isLoading) {
    return (
      <main className="min-h-svh bg-home-background px-4 py-5 text-home-text sm:px-6 sm:py-7 lg:px-8">
        <div className="mx-auto max-w-6xl animate-pulse md:grid md:grid-cols-[14rem_minmax(0,1fr)] md:gap-7">
          <div className="mx-auto aspect-[2/3] w-full max-w-56 rounded-lg bg-home-surface md:mx-0" />
          <div className="mt-5 space-y-4 md:mt-0">
            <div className="h-8 w-3/5 rounded bg-home-surface" />
            <div className="h-5 w-2/5 rounded bg-home-surface" />
            <div className="h-28 rounded bg-home-surface" />
          </div>
        </div>
      </main>
    );
  }

  if (errorMessage || !anime) {
    return (
      <main className="min-h-svh bg-home-background px-4 py-5 text-home-text sm:px-6 sm:py-7 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <p className="text-sm text-home-muted">
            {errorMessage || "Anime not found."}
          </p>
          <Link
            className="mt-4 inline-block text-sm font-semibold text-home-accent"
            href="/"
          >
            Return home
          </Link>
        </div>
      </main>
    );
  }

  const title = anime.title_english || anime.title;
  const hasPoster = anime.image.startsWith(
    "https://cdn.myanimelist.net/images/",
  );
  const totalEpisodes = anime.total_episodes || "?";

  return (
    <main className="min-h-svh bg-home-background px-4 py-5 text-home-text sm:px-6 sm:py-7 lg:px-8">
      <article className="mx-auto max-w-6xl md:grid md:grid-cols-[14rem_minmax(0,1fr)] md:gap-7 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <div className="mx-auto w-full max-w-64 md:mx-0">
          <div className="relative aspect-[2/3] overflow-hidden rounded-lg bg-home-surface">
            {hasPoster ? (
              <Image
                alt={`${title} poster`}
                className="object-cover"
                fill
                quality={100}
                sizes="(max-width: 767px) 16rem, (max-width: 1023px) 14rem, 16rem"
                src={anime.image}
              />
            ) : (
              <div className="flex size-full items-center justify-center px-4 text-center text-sm text-home-muted">
                No poster available
              </div>
            )}
          </div>
        </div>

        <div className="mt-5 min-w-0 md:mt-0">
          <p className="text-sm font-semibold uppercase tracking-wide text-home-accent">
            {anime.status || "Unknown status"}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
            {title}
          </h1>

          {anime.title_english && anime.title_english !== anime.title && (
            <p className="mt-1 text-sm text-home-muted">
              {anime.title}
            </p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {anime.genres.length > 0 ? (
              anime.genres.map((genre) => (
                <span
                  className="rounded-md bg-home-surface px-2 py-1 text-xs"
                  key={genre}
                >
                  {genre}
                </span>
              ))
            ) : (
              <span className="text-sm text-home-muted">
                No genres available
              </span>
            )}
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-x-5 gap-y-4 rounded-lg border border-home-surface bg-home-surface/30 p-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-home-muted">Rating</dt>
              <dd className="mt-1 font-semibold">
                {anime.rating > 0 ? `${anime.rating}/10` : "Not rated"}
              </dd>
            </div>
            <div>
              <dt className="text-home-muted">Popularity</dt>
              <dd className="mt-1 font-semibold">
                {anime.popularity ? `#${anime.popularity}` : "Unranked"}
              </dd>
            </div>
            <div>
              <dt className="text-home-muted">Episodes</dt>
              <dd className="mt-1 font-semibold">
                {anime.current_episodes} / {totalEpisodes}
              </dd>
            </div>
          </dl>

          <section className="mt-6" aria-labelledby="synopsis-title">
            <h2 id="synopsis-title" className="text-lg font-semibold">
              Synopsis
            </h2>
            <p className="mt-2 max-w-5xl text-sm leading-6 text-home-muted sm:text-base">
              {anime.synopsis || "No synopsis available."}
            </p>
          </section>
        </div>
      </article>

      <section
        className="mx-auto mt-8 max-w-6xl border-t border-home-surface pt-6"
        aria-labelledby="episodes-title"
      >
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <h2 id="episodes-title" className="text-xl font-semibold">
              Episodes
            </h2>
            <p className="mt-1 text-sm text-home-muted">
              Select an episode to start watching.
            </p>
          </div>
          <span className="shrink-0 text-sm text-home-muted">
            {episodes.length} {episodes.length === 1 ? "episode" : "episodes"}
          </span>
        </div>

        {episodes.length === 0 ? (
          <p className="text-sm text-home-muted">
            No episodes are available yet.
          </p>
        ) : (
          <>
            <label className="relative mb-4 block max-w-sm">
              <span className="sr-only">Find an episode</span>
              <svg
                aria-hidden="true"
                className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-home-muted"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                viewBox="0 0 20 20"
              >
                <circle cx="8.5" cy="8.5" r="5.5" />
                <path d="m13 13 4 4" />
              </svg>
              <input
                className="h-10 w-full rounded-md border border-home-surface bg-home-surface/30 pr-3 pl-9 text-sm outline-none transition placeholder:text-home-muted focus:border-home-accent"
                onChange={(event) => setEpisodeQuery(event.target.value)}
                placeholder="Find episode number or title"
                type="search"
                value={episodeQuery}
              />
            </label>

            {filteredEpisodes.length === 0 ? (
              <p className="text-sm text-home-muted">
                No episodes match “{episodeQuery.trim()}”.
              </p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {filteredEpisodes.map((episode) => (
                  <Link
                    className="group/episode flex min-w-0 items-center gap-3 rounded-md border border-home-surface bg-home-surface/30 px-3 py-3 transition hover:border-home-accent hover:bg-home-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-home-accent"
                    href={`/watch/${anime.slug}/episode/${episode.episode_number}`}
                    key={episode.id}
                  >
                    <span className="shrink-0 rounded-md bg-home-accent px-2 py-1 text-xs font-bold text-home-background">
                      EP {episode.episode_number}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">
                      {episode.title || `Episode ${episode.episode_number}`}
                    </span>
                    <span
                      aria-hidden="true"
                      className="shrink-0 text-home-muted transition group-hover/episode:translate-x-0.5 group-hover/episode:text-home-accent motion-reduce:transition-none"
                    >
                      →
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}
