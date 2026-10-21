import Image from "next/image";
import Link from "next/link";

import AnimeCardTooltip from "@/components/anime/anime_card_tooltip";
import type { AnimeSummary } from "@/lib/api/anime";

type AnimeCardProps = {
  anime: AnimeSummary;
  episodeNumber?: number;
  href?: string;
  progress?: number;
};

export default function AnimeCard({
  anime,
  episodeNumber,
  href,
  progress,
}: AnimeCardProps) {
  const title = anime.title_english || anime.title;
  const cardHref = href || "/anime/" + anime.slug;
  const hasPoster = anime.image.startsWith(
    "https://cdn.myanimelist.net/images/",
  );
  const status =
    anime.status === "Currently Airing" ? "Airing" : anime.status;
  const progressPercentage =
    typeof progress === "number"
      ? Math.min(Math.max(progress, 0), 100)
      : null;
  const displayedEpisodeNumber =
    episodeNumber ?? anime.current_episodes;

  return (
    <article className="anime-card group relative min-w-0 rounded-md">
      <Link
        aria-describedby={"anime-details-" + anime.id}
        className="block rounded-md outline-none focus-visible:ring-2 focus-visible:ring-home-accent"
        href={cardHref}
      >
        <div className="relative aspect-[2/3] overflow-hidden rounded-md bg-home-surface">
          {hasPoster ? (
            <Image
              src={anime.image}
              alt={`${title} poster`}
              fill
              quality={100}
              sizes="(max-width: 639px) 50vw, (max-width: 767px) 33vw, (max-width: 1023px) 25vw, (max-width: 1279px) 20vw, (max-width: 1535px) 13vw, 12vw"
              className="object-cover transition duration-200 group-hover:scale-[1.02] group-focus-within:scale-[1.02] motion-reduce:transition-none"
            />
          ) : (
            <div className="flex size-full items-center justify-center px-3 text-center text-xs text-home-muted">
              No poster available
            </div>
          )}

          <div className="absolute inset-x-0 bottom-0 flex min-h-7 items-center justify-between gap-2 bg-home-surface/95 px-2 py-1">
            {displayedEpisodeNumber > 0 && (
              <span className="rounded-sm bg-home-accent px-1.5 py-0.5 text-[11px] font-bold leading-none text-home-background">
                EP {displayedEpisodeNumber}
              </span>
            )}
            <span className="ml-auto truncate text-[10px] font-medium uppercase tracking-wide text-home-text/80">
              {status}
            </span>
          </div>

          {progressPercentage !== null && (
            <div
              aria-label={Math.round(progressPercentage) + "% watched"}
              className="absolute inset-x-0 bottom-0 h-1 bg-home-background/60"
            >
              <div
                className="h-full bg-home-accent"
                style={{ width: progressPercentage + "%" }}
              />
            </div>
          )}

          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-home-background/45 opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none">
            <span className="rounded-full border border-home-accent bg-home-background/90 p-2.5 text-home-accent shadow-lg">
              <svg
                aria-hidden="true"
                className="size-5"
                fill="none"
                stroke="currentColor"
                strokeLinejoin="round"
                strokeWidth="1.8"
                viewBox="0 0 24 24"
              >
                <rect height="14" rx="2" width="18" x="3" y="5" />
                <path d="m10 9 5 3-5 3z" />
              </svg>
            </span>
          </div>
        </div>
      </Link>

      <AnimeCardTooltip anime={anime} />

      <h2
        className="mt-2 line-clamp-2 min-h-10 text-sm font-medium leading-5 text-home-text"
        title={title}
      >
        <Link href={cardHref}>{title}</Link>
      </h2>
    </article>
  );
}
