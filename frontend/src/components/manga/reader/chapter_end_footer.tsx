import Link from "next/link";

import { BookIcon, ChevronIcon, HomeIcon } from "@/components/manga/reader/reader_icons";
import {
  getChapterHref,
  type ChapterNavigation,
} from "@/components/manga/reader/reader_settings";
import type { MangaChapter } from "@/lib/api/manga";

type ChapterNavigationCardProps = {
  chapter: MangaChapter | null;
  direction: "next" | "previous";
  slug: string;
};

type ChapterEndFooterProps = {
  chapterNumber: string;
  navigation: ChapterNavigation;
  onLeaveFullscreen: () => void;
  slug: string;
};

const footerLinkClassName =
  "inline-flex h-10 items-center gap-2 rounded-full border border-home-surface bg-home-surface/30 px-4 text-sm font-semibold text-home-muted transition hover:border-home-accent hover:text-home-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-home-accent";

function ChapterNavigationCard({
  chapter,
  direction,
  slug,
}: ChapterNavigationCardProps) {
  const isPrevious = direction === "previous";
  const content = (
    <>
      {isPrevious && <ChevronIcon direction="left" />}
      <span
        className={`min-w-0 flex-1 ${isPrevious ? "text-left" : "text-right"}`}
      >
        <span className="block text-[0.65rem] font-semibold uppercase tracking-widest text-home-muted">
          {isPrevious ? "Previous" : "Next"}
        </span>
        <span className="mt-1 block truncate text-sm font-semibold tabular-nums text-home-text sm:text-base">
          {chapter ? `Ch. ${chapter.chapter_number}` : "Unavailable"}
        </span>
      </span>
      {!isPrevious && <ChevronIcon direction="right" />}
    </>
  );
  const className = (
    "flex min-h-20 min-w-0 items-center gap-3 rounded-xl border "
    + "border-home-surface bg-home-surface/40 px-4 py-3 transition "
    + "focus-visible:outline-2 focus-visible:outline-offset-2 "
    + "focus-visible:outline-home-accent sm:min-h-24 sm:px-5"
  );

  if (!chapter) {
    return (
      <span
        aria-disabled="true"
        className={`${className} cursor-not-allowed opacity-45`}
      >
        {content}
      </span>
    );
  }

  return (
    <Link
      className={`${className} hover:border-home-accent hover:bg-home-surface/70`}
      href={getChapterHref(slug, chapter)}
      title={`${isPrevious ? "Previous" : "Next"} chapter: ${chapter.chapter_number}`}
    >
      {content}
    </Link>
  );
}

export default function ChapterEndFooter({
  chapterNumber,
  navigation,
  onLeaveFullscreen,
  slug,
}: ChapterEndFooterProps) {
  return (
    <footer className="border-t border-home-surface px-4 py-8 sm:px-6 sm:py-10">
      <div className="mx-auto flex max-w-4xl flex-col items-center gap-4">
        <p className="text-base font-semibold text-home-text sm:text-lg">
          End of Ch. {chapterNumber}
        </p>

        <nav
          aria-label="Chapter navigation"
          className="grid w-full grid-cols-2 gap-3"
        >
          <ChapterNavigationCard
            chapter={navigation.previousChapter}
            direction="previous"
            slug={slug}
          />
          <ChapterNavigationCard
            chapter={navigation.nextChapter}
            direction="next"
            slug={slug}
          />
        </nav>

        <div className="flex flex-wrap items-center justify-center gap-2">
          <Link
            className={footerLinkClassName}
            href={`/manga/${slug}`}
            onClick={onLeaveFullscreen}
          >
            <BookIcon />
            Series
          </Link>
          <Link
            className={footerLinkClassName}
            href="/manga"
            onClick={onLeaveFullscreen}
          >
            <HomeIcon />
            Home
          </Link>
        </div>
      </div>
    </footer>
  );
}
