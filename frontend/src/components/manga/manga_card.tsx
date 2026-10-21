import Image from "next/image";
import Link from "next/link";

import MangaCardTooltip from "@/components/manga/manga_card_tooltip";
import type { MangaSummary } from "@/lib/api/manga";

type MangaCardProps = {
  manga: MangaSummary;
  chapterNumber?: string;
  href?: string;
};

export default function MangaCard({
  manga,
  chapterNumber,
  href,
}: MangaCardProps) {
  const title = manga.title_english || manga.title;
  const cardHref = href || "/manga/" + manga.slug;
  const hasPoster = manga.image?.startsWith(
    "https://cdn.myanimelist.net/images/",
  );
  const displayedChapterNumber = chapterNumber || (
    manga.current_chapters > 0 ? String(manga.current_chapters) : ""
  );

  return (
    <article className="manga-card group relative min-w-0 rounded-md">
      <Link
        aria-describedby={`manga-details-${manga.id}`}
        className="block rounded-md outline-none focus-visible:ring-2 focus-visible:ring-home-accent"
        href={cardHref}
      >
        <div className="relative aspect-[2/3] overflow-hidden rounded-md bg-home-surface">
          {hasPoster ? (
            <Image
              src={manga.image}
              alt={`${title} cover`}
              fill
              quality={100}
              sizes="(max-width: 639px) 50vw, (max-width: 767px) 33vw, (max-width: 1023px) 25vw, (max-width: 1279px) 20vw, (max-width: 1535px) 13vw, 12vw"
              className="object-cover transition duration-200 group-hover:scale-[1.02] group-focus-within:scale-[1.02] motion-reduce:transition-none"
            />
          ) : (
            <div className="flex size-full items-center justify-center px-3 text-center text-xs text-home-muted">
              No cover available
            </div>
          )}

          <div className="absolute inset-x-0 bottom-0 flex min-h-7 items-center justify-between gap-2 bg-home-surface/95 px-2 py-1">
            {displayedChapterNumber && (
              <span className="rounded-sm bg-home-accent px-1.5 py-0.5 text-[11px] font-bold leading-none text-home-background">
                CH {displayedChapterNumber}
              </span>
            )}
            <span className="ml-auto truncate text-[10px] font-medium uppercase tracking-wide text-home-text/80">
              {manga.media_type || "Manga"}
            </span>
          </div>

          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-home-background/45 opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none">
            <span className="rounded-full border border-home-accent bg-home-background/90 p-2.5 text-home-accent shadow-lg">
              <svg
                aria-hidden="true"
                className="size-5"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                viewBox="0 0 24 24"
              >
                <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5z" />
                <path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z" />
              </svg>
            </span>
          </div>
        </div>
      </Link>

      <MangaCardTooltip manga={manga} />

      <h2
        className="mt-2 line-clamp-2 min-h-10 text-sm font-medium leading-5 text-home-text"
        title={title}
      >
        <Link href={cardHref}>{title}</Link>
      </h2>
    </article>
  );
}
