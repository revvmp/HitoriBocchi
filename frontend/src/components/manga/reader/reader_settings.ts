import type { MangaChapter } from "@/lib/api/manga";

export type ReadingMode = "right-to-left" | "top-down";

export type ChapterNavigation = {
  nextChapter: MangaChapter | null;
  previousChapter: MangaChapter | null;
};

export const MANGA_READING_MODE_KEY = "hitoribocchi-manga-reading-mode";
export const MANGA_READER_ZOOM_KEY = "hitoribocchi-manga-reader-zoom";
export const DEFAULT_READER_ZOOM = 1;
export const MAX_READER_ZOOM = 2;
export const MIN_READER_ZOOM = 0.5;
export const MANGA_PAGE_PREFETCH_COUNT = 2;
export const READER_ZOOM_STEP = 0.1;

export function normalizeZoom(value: number) {
  return Number(
    Math.min(MAX_READER_ZOOM, Math.max(MIN_READER_ZOOM, value)).toFixed(1),
  );
}

export function getChapterHref(slug: string, chapter: MangaChapter) {
  return `/manga/${slug}/chapter/${encodeURIComponent(chapter.chapter_number)}`;
}

export function isReaderControlTarget(target: EventTarget | null) {
  return target instanceof Element && Boolean(
    target.closest("a, button, details, summary, [data-reader-controls]"),
  );
}
