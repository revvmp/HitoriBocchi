"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import ChapterEndFooter from "@/components/manga/reader/chapter_end_footer";
import MangaPageImage from "@/components/manga/reader/manga_page_image";
import PageProgressIndicator from "@/components/manga/reader/page_progress_indicator";
import ReaderHud from "@/components/manga/reader/reader_hud";
import { ChevronIcon } from "@/components/manga/reader/reader_icons";
import type {
  ChapterNavigation,
  ReadingMode,
} from "@/components/manga/reader/reader_settings";
import useActivePageObserver from "@/components/manga/reader/use_active_page_observer";
import useBrowserFullscreen from "@/components/manga/reader/use_browser_fullscreen";
import usePagePrefetch from "@/components/manga/reader/use_page_prefetch";
import { usePagedSwipe, useReaderControlsToggle } from "@/components/manga/reader/use_reader_gestures";
import useReaderKeyboard from "@/components/manga/reader/use_reader_keyboard";
import useReaderPreferences from "@/components/manga/reader/use_reader_preferences";
import {
  getMangaReader,
  type MangaChapter,
  type MangaPage,
  type MangaSummary,
} from "@/lib/api/manga";
import { ApiError } from "@/lib/api/client";

type MangaReaderProps = {
  chapterNumber: string;
  slug: string;
};

export default function MangaReader({
  chapterNumber,
  slug,
}: MangaReaderProps) {
  const router = useRouter();
  const [manga, setManga] = useState<MangaSummary | null>(null);
  const [chapter, setChapter] = useState<MangaChapter | null>(null);
  const [chapters, setChapters] = useState<MangaChapter[]>([]);
  const [pages, setPages] = useState<MangaPage[]>([]);
  const [failedPages, setFailedPages] = useState<Set<number>>(new Set());
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [activePageIndex, setActivePageIndex] = useState(0);
  const [areReaderControlsVisible, setAreReaderControlsVisible] = useState(true);
  const [isReaderSettingsOpen, setIsReaderSettingsOpen] = useState(false);
  const topDownReaderRef = useRef<HTMLDivElement>(null);
  const pagedReaderRef = useRef<HTMLElement>(null);
  const {
    handleZoomChange,
    readingMode,
    saveReadingMode,
    zoomLevel,
  } = useReaderPreferences();
  const resetPagePrefetches = usePagePrefetch(pages, activePageIndex);
  const fullscreen = useBrowserFullscreen();

  useEffect(() => {
    let isActive = true;

    getMangaReader(slug, chapterNumber)
      .then((response) => {
        if (!isActive) {
          return;
        }

        setManga(response.manga);
        setChapter(response.chapter);
        setChapters(response.chapters);
        resetPagePrefetches();
        setActivePageIndex(0);
        setFailedPages(new Set());
        setPages(response.pages);
      })
      .catch((error) => {
        if (!isActive) {
          return;
        }

        if (error instanceof ApiError && [401, 403].includes(error.status)) {
          router.replace(
            `/login?next=/manga/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(chapterNumber)}`,
          );
          return;
        }

        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Unable to load chapter",
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
  }, [chapterNumber, resetPagePrefetches, router, slug]);

  useEffect(() => {
    const documentRoot = document.documentElement;
    documentRoot.classList.add("manga-reader-active");
    document.body.classList.add("manga-reader-route");

    return () => {
      documentRoot.classList.remove("manga-reader-active");
      document.body.classList.remove("manga-reader-route");
    };
  }, []);

  useActivePageObserver(
    topDownReaderRef,
    pages,
    readingMode,
    setActivePageIndex,
  );

  // Chapters are ordered newest first, so the next chapter precedes this one.
  const navigation = useMemo<ChapterNavigation>(() => {
    if (!chapter) {
      return { nextChapter: null, previousChapter: null };
    }

    const currentIndex = chapters.findIndex(
      (item) => item.id === chapter.id,
    );

    if (currentIndex < 0) {
      return { nextChapter: null, previousChapter: null };
    }

    return {
      nextChapter: chapters[currentIndex - 1] ?? null,
      previousChapter: chapters[currentIndex + 1] ?? null,
    };
  }, [chapter, chapters]);

  const scrollPagedReaderToTop = useCallback(() => {
    window.requestAnimationFrame(() => {
      pagedReaderRef.current?.scrollIntoView({ block: "start" });
    });
  }, []);

  const goToNextPage = useCallback(() => {
    if (activePageIndex + 1 >= pages.length) {
      return;
    }

    setActivePageIndex(activePageIndex + 1);
    scrollPagedReaderToTop();
  }, [activePageIndex, pages.length, scrollPagedReaderToTop]);

  const goToPreviousPage = useCallback(() => {
    if (activePageIndex === 0) {
      return;
    }

    setActivePageIndex(activePageIndex - 1);
    scrollPagedReaderToTop();
  }, [activePageIndex, scrollPagedReaderToTop]);

  const handleReadingModeChange = useCallback((nextMode: ReadingMode) => {
    setIsReaderSettingsOpen(false);

    if (nextMode === readingMode) {
      return;
    }

    saveReadingMode(nextMode);
    setActivePageIndex(0);
    window.requestAnimationFrame(() => window.scrollTo({ top: 0 }));
  }, [readingMode, saveReadingMode]);

  const toggleReaderControls = useCallback(() => {
    setAreReaderControlsVisible((areVisible) => !areVisible);
    setIsReaderSettingsOpen(false);
  }, []);

  const readerControlsToggleHandlers =
    useReaderControlsToggle(toggleReaderControls);
  const pagedSwipeHandlers = usePagedSwipe(goToNextPage, goToPreviousPage);

  useReaderKeyboard({
    goToNextPage,
    goToPreviousPage,
    navigation,
    onZoomChange: handleZoomChange,
    readingMode,
    slug,
    zoomLevel,
  });

  function markPageFailed(pageNumber: number) {
    setFailedPages((current) => {
      const nextPages = new Set(current);
      nextPages.add(pageNumber);
      return nextPages;
    });
  }

  if (isLoading) {
    return (
      <main className="manga-reader min-h-svh bg-home-background text-home-text">
        <div className="mx-auto max-w-4xl animate-pulse">
          <div className="mx-auto aspect-[2/3] max-w-3xl bg-home-surface" />
        </div>
      </main>
    );
  }

  if (errorMessage || !manga || !chapter) {
    return (
      <main className="manga-reader min-h-svh bg-home-background px-4 py-6 text-home-text">
        <div className="mx-auto max-w-4xl rounded-lg border border-home-surface bg-home-surface/30 p-5">
          <p className="text-sm text-home-muted">
            {errorMessage || "Chapter not found."}
          </p>
          <Link
            className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-home-accent"
            href={`/manga/${slug}`}
          >
            <ChevronIcon direction="left" />
            Return to manga details
          </Link>
        </div>
      </main>
    );
  }

  const title = manga.title_english || manga.title;
  const latestChapterNumber = chapters[0]?.chapter_number || chapter.chapter_number;
  const activePage = pages[activePageIndex] ?? pages[0] ?? null;
  const isLastPage = activePageIndex + 1 >= pages.length;
  const zoomStyle = {
    maxWidth: `${56 * zoomLevel}rem`,
    width: `${zoomLevel * 100}%`,
  };

  return (
    <main
      className="manga-reader min-h-svh touch-manipulation select-none bg-home-background text-home-text"
      {...readerControlsToggleHandlers}
    >
      <PageProgressIndicator
        activePageIndex={activePageIndex}
        pages={pages}
      />

      {areReaderControlsVisible && (
        <ReaderHud
          canUseBrowserFullscreen={fullscreen.canUseBrowserFullscreen}
          chapterNumber={chapter.chapter_number}
          isBrowserFullscreen={fullscreen.isBrowserFullscreen}
          isSettingsOpen={isReaderSettingsOpen}
          latestChapterNumber={latestChapterNumber}
          navigation={navigation}
          onLeaveFullscreen={fullscreen.leaveReaderFullscreen}
          onReadingModeChange={handleReadingModeChange}
          onToggleBrowserFullscreen={() => void fullscreen.toggleBrowserFullscreen()}
          onToggleSettings={() => setIsReaderSettingsOpen((isOpen) => !isOpen)}
          onZoomChange={handleZoomChange}
          readingMode={readingMode}
          slug={manga.slug}
          zoomLevel={zoomLevel}
        />
      )}

      {pages.length === 0 ? (
        <div className="mx-auto max-w-4xl px-4 py-16 text-center">
          <p className="text-sm text-home-muted">
            No readable pages were returned for this chapter.
          </p>
        </div>
      ) : readingMode === "top-down" ? (
        <section
          aria-label={`${title} chapter ${chapter.chapter_number} pages`}
          className="w-full overflow-x-auto overscroll-x-contain"
        >
          <div
            className="mx-auto"
            ref={topDownReaderRef}
            style={zoomStyle}
          >
            {pages.map((page, index) => (
              <div data-reader-page-index={index} key={page.page}>
                <MangaPageImage
                  chapterNumber={chapter.chapter_number}
                  className="block h-auto w-full"
                  eager={index === 0}
                  failed={failedPages.has(page.page)}
                  onError={() => markPageFailed(page.page)}
                  page={page}
                  sizes="100vw"
                  title={title}
                />
              </div>
            ))}
          </div>
        </section>
      ) : activePage ? (
        <section
          aria-label={`${title} chapter ${chapter.chapter_number}, right-to-left reader`}
          className="mx-auto flex min-h-svh w-full max-w-5xl touch-pan-y flex-col items-center justify-center px-0 py-4 sm:px-4 sm:py-6"
          ref={pagedReaderRef}
          {...pagedSwipeHandlers}
        >
          <div className="w-full overflow-x-auto overscroll-x-contain">
            <div
              className="mx-auto flex items-start justify-center"
              style={zoomStyle}
            >
              <MangaPageImage
                chapterNumber={chapter.chapter_number}
                className="block h-auto w-full object-contain"
                eager
                failed={failedPages.has(activePage.page)}
                onError={() => markPageFailed(activePage.page)}
                page={activePage}
                sizes="100vw"
                title={title}
              />
            </div>
          </div>

          <div
            aria-label="Page navigation"
            className="mt-4 flex w-full max-w-sm items-center gap-2 rounded-lg border border-home-surface bg-home-surface/20 p-1.5"
            role="group"
          >
            <button
              aria-label="Previous page"
              className="flex h-10 min-w-0 flex-1 items-center justify-center gap-1.5 rounded-md border border-home-surface px-3 text-sm font-semibold text-home-muted transition hover:border-home-accent hover:text-home-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-home-accent disabled:cursor-not-allowed disabled:opacity-40"
              disabled={activePageIndex === 0}
              onClick={goToPreviousPage}
              title="Previous page (Left Arrow)"
              type="button"
            >
              <ChevronIcon direction="left" />
              <span>Prev</span>
            </button>
            <span
              aria-live="polite"
              className="min-w-20 text-center text-xs font-medium tabular-nums text-home-muted"
            >
              Page {activePageIndex + 1} / {pages.length}
            </span>
            <button
              aria-label="Next page"
              className="flex h-10 min-w-0 flex-1 items-center justify-center gap-1.5 rounded-md bg-home-accent px-3 text-sm font-semibold text-home-background transition hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-home-accent disabled:cursor-not-allowed disabled:opacity-40"
              disabled={isLastPage}
              onClick={goToNextPage}
              title="Next page (Right Arrow)"
              type="button"
            >
              <span>Next</span>
              <ChevronIcon direction="right" />
            </button>
          </div>
          <p className="mt-2 px-4 text-center text-xs text-home-muted">
            Swipe right for the next page and left for the previous page.
          </p>
        </section>
      ) : null}

      {pages.length > 0
        && (readingMode === "top-down" || isLastPage)
        && (
          <ChapterEndFooter
            chapterNumber={chapter.chapter_number}
            navigation={navigation}
            onLeaveFullscreen={fullscreen.leaveReaderFullscreen}
            slug={manga.slug}
          />
        )}
    </main>
  );
}
