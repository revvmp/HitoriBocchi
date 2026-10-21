"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import * as readerSettings from "@/components/manga/reader/reader_settings";

type UseReaderKeyboardOptions = {
  goToNextPage: () => void;
  goToPreviousPage: () => void;
  navigation: readerSettings.ChapterNavigation;
  onZoomChange: (nextZoom: number) => void;
  readingMode: readerSettings.ReadingMode;
  slug: string;
  zoomLevel: number;
};

// Arrow keys turn pages in the paged reader, +/-/0 zoom, and N/B change chapters.
export default function useReaderKeyboard({
  goToNextPage,
  goToPreviousPage,
  navigation,
  onZoomChange,
  readingMode,
  slug,
  zoomLevel,
}: UseReaderKeyboardOptions) {
  const router = useRouter();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;

      if (target?.matches("input, textarea, select, button, a")) {
        return;
      }

      if (readingMode === "right-to-left") {
        if (event.key === "ArrowRight") {
          event.preventDefault();
          goToNextPage();
          return;
        }

        if (event.key === "ArrowLeft") {
          event.preventDefault();
          goToPreviousPage();
          return;
        }
      }

      if (event.key === "+" || event.key === "=") {
        event.preventDefault();
        onZoomChange(zoomLevel + readerSettings.READER_ZOOM_STEP);
        return;
      }

      if (event.key === "-") {
        event.preventDefault();
        onZoomChange(zoomLevel - readerSettings.READER_ZOOM_STEP);
        return;
      }

      if (event.key === "0") {
        event.preventDefault();
        onZoomChange(readerSettings.DEFAULT_READER_ZOOM);
        return;
      }

      if (event.key.toLocaleLowerCase() === "n" && navigation.nextChapter) {
        router.push(readerSettings.getChapterHref(slug, navigation.nextChapter));
      }

      if (
        event.key.toLocaleLowerCase() === "b"
        && navigation.previousChapter
      ) {
        router.push(readerSettings.getChapterHref(slug, navigation.previousChapter));
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    goToNextPage,
    goToPreviousPage,
    navigation,
    onZoomChange,
    readingMode,
    router,
    slug,
    zoomLevel,
  ]);
}
