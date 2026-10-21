"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  getMangaBookmark,
  getMangaDetails,
  updateMangaBookmark,
  type MangaChapter,
  type MangaSummary,
} from "@/lib/api/manga";
import { ApiError } from "@/lib/api/client";

type MangaDetailsProps = {
  slug: string;
};

export default function MangaDetails({ slug }: MangaDetailsProps) {
  const router = useRouter();
  const [manga, setManga] = useState<MangaSummary | null>(null);
  const [chapters, setChapters] = useState<MangaChapter[]>([]);
  const [chapterQuery, setChapterQuery] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [bookmarkMessage, setBookmarkMessage] = useState("");
  const [isBookmarked, setIsBookmarked] = useState(false);
  const [isBookmarkAvailable, setIsBookmarkAvailable] = useState(true);
  const [isBookmarkLoading, setIsBookmarkLoading] = useState(true);
  const [isBookmarkUpdating, setIsBookmarkUpdating] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isActive = true;

    getMangaDetails(slug)
      .then((response) => {
        if (!isActive) {
          return;
        }

        setManga(response.manga);
        setChapters(response.chapters);
      })
      .catch((error) => {
        if (!isActive) {
          return;
        }

        if (error instanceof ApiError && [401, 403].includes(error.status)) {
          router.replace(`/login?next=/manga/${encodeURIComponent(slug)}`);
          return;
        }

        setErrorMessage(
          error instanceof Error ? error.message : "Unable to load manga",
        );
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    getMangaBookmark(slug)
      .then((response) => {
        if (isActive) {
          setIsBookmarked(response.is_bookmarked);
        }
      })
      .catch((error) => {
        if (
          isActive &&
          error instanceof ApiError &&
          [401, 403].includes(error.status)
        ) {
          setIsBookmarkAvailable(false);
        }
      })
      .finally(() => {
        if (isActive) {
          setIsBookmarkLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [router, slug]);

  const filteredChapters = useMemo(() => {
    const normalizedQuery = chapterQuery.trim().toLocaleLowerCase();

    if (!normalizedQuery) {
      return chapters;
    }

    return chapters.filter((chapter) => (
      chapter.chapter_number.toLocaleLowerCase().includes(normalizedQuery) ||
      chapter.title.toLocaleLowerCase().includes(normalizedQuery)
    ));
  }, [chapterQuery, chapters]);

  async function handleBookmarkUpdate() {
    if (isBookmarkUpdating) {
      return;
    }

    setBookmarkMessage("");
    setIsBookmarkUpdating(true);

    try {
      const response = await updateMangaBookmark(slug, isBookmarked);
      setIsBookmarked(response.is_bookmarked);
      setBookmarkMessage(
        response.is_bookmarked
          ? "Added to your bookmarks."
          : "Removed from your bookmarks.",
      );
    } catch (error) {
      if (error instanceof ApiError && [401, 403].includes(error.status)) {
        router.push(`/login?next=/manga/${encodeURIComponent(slug)}`);
        return;
      }

      setBookmarkMessage(
        error instanceof Error
          ? error.message
          : "Unable to update bookmark",
      );
    } finally {
      setIsBookmarkUpdating(false);
    }
  }

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

  if (errorMessage || !manga) {
    return (
      <main className="min-h-svh bg-home-background px-4 py-5 text-home-text sm:px-6 sm:py-7 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <p className="text-sm text-home-muted">
            {errorMessage || "Manga not found."}
          </p>
          <Link
            className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-home-accent"
            href="/manga"
          >
            <span aria-hidden="true">←</span>
            Return to manga
          </Link>
        </div>
      </main>
    );
  }

  const title = manga.title_english || manga.title;
  const hasPoster = manga.image?.startsWith(
    "https://cdn.myanimelist.net/images/",
  );
  const newestChapter = chapters[0];
  const oldestChapter = chapters[chapters.length - 1];
  const currentChapters = newestChapter?.chapter_number || manga.current_chapters;
  const malTotalChapters = manga.total_chapters || "?";
  const currentChapterNumber = Number(currentChapters);
  const malTotalChapterNumber = Number(malTotalChapters);
  const totalChapters = Number.isFinite(currentChapterNumber)
    && Number.isFinite(malTotalChapterNumber)
    && currentChapterNumber > malTotalChapterNumber
    ? currentChapters
    : malTotalChapters;

  return (
    <main className="min-h-svh bg-home-background px-4 py-5 text-home-text sm:px-6 sm:py-7 lg:px-8">
      <article className="mx-auto max-w-6xl md:grid md:grid-cols-[14rem_minmax(0,1fr)] md:gap-7 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <div className="mx-auto w-full max-w-64 md:mx-0">
          <div className="relative aspect-[2/3] overflow-hidden rounded-lg bg-home-surface shadow-xl">
            {hasPoster ? (
              <Image
                alt={`${title} cover`}
                className="object-cover"
                fill
                quality={100}
                sizes="(max-width: 767px) 16rem, (max-width: 1023px) 14rem, 16rem"
                src={manga.image}
              />
            ) : (
              <div className="flex size-full items-center justify-center px-4 text-center text-sm text-home-muted">
                No cover available
              </div>
            )}
          </div>

          {isBookmarkLoading ? (
            <div className="mt-3 h-11 animate-pulse rounded-md bg-home-surface" />
          ) : isBookmarkAvailable ? (
            <button
              aria-pressed={isBookmarked}
              className={`mt-3 flex h-11 w-full items-center justify-center gap-2 rounded-md border px-4 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-home-accent disabled:cursor-not-allowed disabled:opacity-60 ${
                isBookmarked
                  ? "border-home-accent bg-home-accent text-home-background"
                  : "border-home-surface bg-home-surface/30 text-home-text hover:border-home-accent hover:bg-home-surface"
              }`}
              disabled={isBookmarkUpdating}
              onClick={handleBookmarkUpdate}
              type="button"
            >
              <svg
                aria-hidden="true"
                className="size-4"
                fill={isBookmarked ? "currentColor" : "none"}
                stroke="currentColor"
                strokeLinejoin="round"
                strokeWidth="1.8"
                viewBox="0 0 24 24"
              >
                <path d="M6 3h12v18l-6-4-6 4z" />
              </svg>
              {isBookmarkUpdating
                ? "Updating..."
                : isBookmarked
                  ? "Bookmarked"
                  : "Add bookmark"}
            </button>
          ) : (
            <Link
              className="mt-3 flex h-11 w-full items-center justify-center gap-2 rounded-md border border-home-surface bg-home-surface/30 px-4 text-sm font-semibold transition hover:border-home-accent hover:bg-home-surface"
              href={`/login?next=/manga/${encodeURIComponent(slug)}`}
            >
              Sign in to bookmark
            </Link>
          )}

          <p
            aria-live="polite"
            className="mt-1 min-h-5 text-center text-xs text-home-muted"
          >
            {bookmarkMessage}
          </p>
        </div>

        <div className="mt-5 min-w-0 md:mt-0">
          <div className="flex flex-wrap items-center gap-2 text-sm font-semibold uppercase tracking-wide text-home-accent">
            <span>{manga.status || "Unknown status"}</span>
            <span aria-hidden="true" className="size-1 rounded-full bg-home-muted" />
            <span>{manga.media_type || "Manga"}</span>
          </div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
            {title}
          </h1>

          {manga.title_english && manga.title_english !== manga.title && (
            <p className="mt-1 text-sm text-home-muted">{manga.title}</p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {manga.genres.length > 0 ? (
              manga.genres.map((genre) => (
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
                {manga.rating > 0 ? `${manga.rating}/10` : "Not rated"}
              </dd>
            </div>
            <div>
              <dt className="text-home-muted">Popularity</dt>
              <dd className="mt-1 font-semibold">
                {manga.popularity ? `#${manga.popularity}` : "Unranked"}
              </dd>
            </div>
            <div>
              <dt className="text-home-muted">Chapters</dt>
              <dd className="mt-1 font-semibold">
                {currentChapters} / {totalChapters}
              </dd>
            </div>
          </dl>

          {chapters.length > 0 && (
            <div className="mt-5 flex flex-col gap-2 sm:flex-row">
              {oldestChapter && (
                <Link
                  className="flex h-11 flex-1 items-center justify-center gap-2 rounded-md bg-home-text px-4 text-sm font-semibold text-home-background transition hover:opacity-90"
                  href={`/manga/${manga.slug}/chapter/${encodeURIComponent(oldestChapter.chapter_number)}`}
                >
                  <span aria-hidden="true">▶</span>
                  Start reading
                </Link>
              )}
              {newestChapter && newestChapter.id !== oldestChapter?.id && (
                <Link
                  className="flex h-11 flex-1 items-center justify-center gap-2 rounded-md border border-home-surface bg-home-surface/30 px-4 text-sm font-semibold transition hover:border-home-accent hover:bg-home-surface"
                  href={`/manga/${manga.slug}/chapter/${encodeURIComponent(newestChapter.chapter_number)}`}
                >
                  Latest: Ch. {newestChapter.chapter_number}
                  <span aria-hidden="true">→</span>
                </Link>
              )}
            </div>
          )}

          <section className="mt-6" aria-labelledby="manga-synopsis-title">
            <h2 id="manga-synopsis-title" className="text-lg font-semibold">
              Synopsis
            </h2>
            <p className="mt-2 max-w-5xl text-sm leading-6 text-home-muted sm:text-base">
              {manga.synopsis || "No synopsis available."}
            </p>
          </section>
        </div>
      </article>

      <section
        className="mx-auto mt-8 max-w-6xl border-t border-home-surface pt-6"
        aria-labelledby="manga-chapters-title"
      >
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 id="manga-chapters-title" className="text-xl font-semibold">
              Chapters
            </h2>
            <p className="mt-1 text-sm text-home-muted">
              Select a chapter to read from top to bottom.
            </p>
          </div>
          <span className="shrink-0 text-sm text-home-muted">
            {chapters.length} {chapters.length === 1 ? "chapter" : "chapters"}
          </span>
        </div>

        {chapters.length === 0 ? (
          <div className="rounded-md border border-dashed border-home-surface p-6 text-center">
            <p className="text-sm text-home-muted">
              No chapters are available yet.
            </p>
          </div>
        ) : (
          <>
            <label className="relative mb-4 block max-w-sm">
              <span className="sr-only">Find a chapter</span>
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
                onChange={(event) => setChapterQuery(event.target.value)}
                placeholder="Find chapter number or title"
                type="search"
                value={chapterQuery}
              />
            </label>

            {filteredChapters.length === 0 ? (
              <p className="text-sm text-home-muted">
                No chapters match “{chapterQuery.trim()}”.
              </p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {filteredChapters.map((chapter) => (
                  <Link
                    className="group/chapter flex min-w-0 items-center gap-3 rounded-md border border-home-surface bg-home-surface/30 px-3 py-3 transition hover:border-home-accent hover:bg-home-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-home-accent"
                    href={`/manga/${manga.slug}/chapter/${encodeURIComponent(chapter.chapter_number)}`}
                    key={chapter.id}
                  >
                    <span className="shrink-0 rounded-md bg-home-accent px-2 py-1 text-xs font-bold text-home-background">
                      CH {chapter.chapter_number}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">
                      {chapter.title || `Chapter ${chapter.chapter_number}`}
                    </span>
                    <span
                      aria-hidden="true"
                      className="shrink-0 text-home-muted transition group-hover/chapter:translate-x-0.5 group-hover/chapter:text-home-accent motion-reduce:transition-none"
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
