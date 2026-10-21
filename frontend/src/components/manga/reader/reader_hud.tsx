import Link from "next/link";

import {
  BookIcon,
  ChevronIcon,
  FullscreenIcon,
  HomeIcon,
  SettingsIcon,
} from "@/components/manga/reader/reader_icons";
import {
  getChapterHref,
  type ChapterNavigation,
  type ReadingMode,
} from "@/components/manga/reader/reader_settings";
import ZoomControls from "@/components/manga/reader/zoom_controls";
import type { MangaChapter } from "@/lib/api/manga";

type ReaderHudProps = {
  canUseBrowserFullscreen: boolean;
  chapterNumber: string;
  isBrowserFullscreen: boolean;
  isSettingsOpen: boolean;
  latestChapterNumber: string;
  navigation: ChapterNavigation;
  onLeaveFullscreen: () => void;
  onReadingModeChange: (nextMode: ReadingMode) => void;
  onToggleBrowserFullscreen: () => void;
  onToggleSettings: () => void;
  onZoomChange: (nextZoom: number) => void;
  readingMode: ReadingMode;
  slug: string;
  zoomLevel: number;
};

type HudChapterLinkProps = {
  chapter: MangaChapter | null;
  direction: "next" | "previous";
  slug: string;
};

const READER_HUD_BUTTON_CLASS = "flex size-10 items-center justify-center text-home-muted transition hover:bg-home-surface hover:text-home-text focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-home-accent disabled:cursor-not-allowed disabled:opacity-35";

function getReadingModeButtonClass(isActive: boolean) {
  return `flex min-h-11 min-w-0 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-home-accent ${
    isActive
      ? "border-home-accent bg-home-accent text-home-background"
      : "border-home-surface bg-home-surface/30 text-home-muted hover:border-home-accent hover:text-home-text"
  }`;
}

function HudChapterLink({ chapter, direction, slug }: HudChapterLinkProps) {
  const label = direction === "previous" ? "Previous" : "Next";
  const iconDirection = direction === "previous" ? "left" : "right";

  if (!chapter) {
    return (
      <span
        aria-hidden="true"
        className="flex h-full w-9 items-center justify-center text-home-muted opacity-35"
      >
        <ChevronIcon direction={iconDirection} />
      </span>
    );
  }

  return (
    <Link
      aria-label={`${label} chapter, chapter ${chapter.chapter_number}`}
      className="flex h-full w-9 items-center justify-center text-home-muted transition hover:bg-home-surface hover:text-home-text focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-home-accent"
      href={getChapterHref(slug, chapter)}
      title={`${label} chapter: ${chapter.chapter_number}`}
    >
      <ChevronIcon direction={iconDirection} />
    </Link>
  );
}

export default function ReaderHud({
  canUseBrowserFullscreen,
  chapterNumber,
  isBrowserFullscreen,
  isSettingsOpen,
  latestChapterNumber,
  navigation,
  onLeaveFullscreen,
  onReadingModeChange,
  onToggleBrowserFullscreen,
  onToggleSettings,
  onZoomChange,
  readingMode,
  slug,
  zoomLevel,
}: ReaderHudProps) {
  const fullscreenLabel = isBrowserFullscreen
    ? "Exit browser fullscreen"
    : "Enter browser fullscreen";

  return (
    <>
      <nav
        aria-label="Chapter navigation"
        className="fixed top-3 right-4 z-[70] inline-flex h-9 items-center overflow-hidden rounded-md border border-home-surface bg-home-background/90 shadow-lg backdrop-blur-sm"
        data-reader-controls
      >
        <HudChapterLink
          chapter={navigation.previousChapter}
          direction="previous"
          slug={slug}
        />
        <span className="flex h-full min-w-24 items-center justify-center border-x border-home-surface px-2 text-[0.7rem] font-semibold tabular-nums text-home-text">
          Ch. {chapterNumber}
          <span className="ml-1 text-home-muted">/ {latestChapterNumber}</span>
        </span>
        <HudChapterLink
          chapter={navigation.nextChapter}
          direction="next"
          slug={slug}
        />
      </nav>

      <nav
        aria-label="Reader shortcuts"
        className="fixed top-14 right-4 z-[70] flex flex-col overflow-hidden rounded-md border border-home-surface bg-home-background/90 shadow-lg backdrop-blur-sm"
        data-reader-controls
      >
        <Link
          aria-label="Manga home"
          className={READER_HUD_BUTTON_CLASS}
          href="/manga"
          onClick={onLeaveFullscreen}
          title="Manga home"
        >
          <HomeIcon />
        </Link>
        <Link
          aria-label="Manga details"
          className={`${READER_HUD_BUTTON_CLASS} border-t border-home-surface`}
          href={`/manga/${slug}`}
          onClick={onLeaveFullscreen}
          title="Manga details"
        >
          <BookIcon />
        </Link>
        <button
          aria-controls="reader-hud-settings"
          aria-expanded={isSettingsOpen}
          aria-label="Reader settings"
          className={`${READER_HUD_BUTTON_CLASS} border-t border-home-surface`}
          onClick={onToggleSettings}
          title="Reader settings"
          type="button"
        >
          <SettingsIcon />
        </button>
        {canUseBrowserFullscreen && (
          <button
            aria-label={fullscreenLabel}
            className={`${READER_HUD_BUTTON_CLASS} hidden border-t border-home-surface lg:flex`}
            onClick={onToggleBrowserFullscreen}
            title={fullscreenLabel}
            type="button"
          >
            <FullscreenIcon isActive={isBrowserFullscreen} />
          </button>
        )}
      </nav>

      {isSettingsOpen && (
        <aside
          aria-label="Reader settings"
          className="fixed inset-x-3 bottom-3 z-[80] rounded-lg border border-home-surface bg-home-background/95 p-3 shadow-xl backdrop-blur-sm sm:inset-x-auto sm:top-14 sm:right-16 sm:bottom-auto sm:w-72"
          data-reader-controls
          id="reader-hud-settings"
        >
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-home-muted">
            Reading style
          </p>
          <div
            aria-label="Reading style"
            className="grid grid-cols-2 gap-2"
            role="group"
          >
            <button
              aria-pressed={readingMode === "top-down"}
              className={getReadingModeButtonClass(
                readingMode === "top-down",
              )}
              onClick={() => onReadingModeChange("top-down")}
              type="button"
            >
              Top down
            </button>
            <button
              aria-pressed={readingMode === "right-to-left"}
              className={getReadingModeButtonClass(
                readingMode === "right-to-left",
              )}
              onClick={() => onReadingModeChange("right-to-left")}
              type="button"
            >
              Right to left
            </button>
          </div>
        </aside>
      )}

      <div
        className="fixed right-3 bottom-3 z-[70] hidden rounded-lg border border-home-surface bg-home-background/90 p-1.5 shadow-lg backdrop-blur-sm lg:block"
        data-reader-controls
      >
        <ZoomControls
          onZoomChange={onZoomChange}
          zoomLevel={zoomLevel}
        />
      </div>
    </>
  );
}
