import Link from "next/link";

import type { AnimeEpisode } from "@/lib/api/anime";

type EpisodeNavigationProps = {
  animeSlug: string;
  nextEpisode?: AnimeEpisode;
  previousEpisode?: AnimeEpisode;
};

export default function EpisodeNavigation({
  animeSlug,
  nextEpisode,
  previousEpisode,
}: EpisodeNavigationProps) {
  return (
    <nav
      className="mt-5 grid grid-cols-[minmax(0,16rem)_auto_minmax(0,16rem)] justify-center gap-3 sm:gap-5"
      aria-label="Episode navigation"
    >
      {previousEpisode ? (
        <Link
          className="w-full rounded-md border border-home-surface bg-home-surface/30 px-3 py-2 text-sm font-semibold transition hover:border-home-accent hover:bg-home-surface"
          href={`/watch/${animeSlug}/episode/${previousEpisode.episode_number}`}
        >
          <span className="block text-xs font-normal text-home-muted">
            Previous
          </span>
          Episode {previousEpisode.episode_number}
        </Link>
      ) : (
        <span className="w-full rounded-md border border-home-surface px-3 py-2 text-sm text-home-muted opacity-60">
          <span className="block text-xs">Previous</span>
          No earlier episode
        </span>
      )}

      <Link
        className="self-center justify-self-center rounded-md bg-home-accent px-6 py-2.5 text-sm font-semibold text-home-background transition hover:opacity-90"
        href={`/anime/${animeSlug}`}
      >
        All episodes
      </Link>

      {nextEpisode ? (
        <Link
          className="w-full rounded-md border border-home-surface bg-home-surface/30 px-3 py-2 text-right text-sm font-semibold transition hover:border-home-accent hover:bg-home-surface"
          href={`/watch/${animeSlug}/episode/${nextEpisode.episode_number}`}
        >
          <span className="block text-xs font-normal text-home-muted">
            Next
          </span>
          Episode {nextEpisode.episode_number}
        </Link>
      ) : (
        <span className="w-full rounded-md border border-home-surface px-3 py-2 text-right text-sm text-home-muted opacity-60">
          <span className="block text-xs">Next</span>
          Latest episode
        </span>
      )}
    </nav>
  );
}
