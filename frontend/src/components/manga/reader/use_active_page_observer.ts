"use client";

import { useEffect, type RefObject } from "react";

import type { ReadingMode } from "@/components/manga/reader/reader_settings";
import type { MangaPage } from "@/lib/api/manga";

// Tracks the page closest to the viewport center in the top-down reader.
export default function useActivePageObserver(readerRef: RefObject<HTMLDivElement | null>, pages: MangaPage[], readingMode: ReadingMode, onActivePageChange: (pageIndex: number) => void) {
  useEffect(() => {
    const reader = readerRef.current;
    if (
      readingMode !== "top-down"
      || pages.length === 0
      || !reader
    ) {
      return;
    }

    const pageElements = Array.from(
      reader.querySelectorAll<HTMLElement>("[data-reader-page-index]"),
    );
    const observer = new IntersectionObserver((entries) => {
      const viewportCenter = window.innerHeight / 2;
      const currentEntry = entries
        .filter((entry) => entry.isIntersecting)
        .sort((firstEntry, secondEntry) => {
          const firstCenter = (
            firstEntry.boundingClientRect.top
            + firstEntry.boundingClientRect.bottom
          ) / 2;
          const secondCenter = (
            secondEntry.boundingClientRect.top
            + secondEntry.boundingClientRect.bottom
          ) / 2;
          return (
            Math.abs(firstCenter - viewportCenter)
            - Math.abs(secondCenter - viewportCenter)
          );
        })[0];

      if (!(currentEntry?.target instanceof HTMLElement)) {
        return;
      }

      const nextPageIndex = Number.parseInt(
        currentEntry.target.dataset.readerPageIndex || "",
        10,
      );
      if (Number.isInteger(nextPageIndex)) {
        onActivePageChange(nextPageIndex);
      }
    }, {
      rootMargin: "-45% 0px -45% 0px",
      threshold: 0,
    });

    pageElements.forEach((pageElement) => observer.observe(pageElement));
    return () => observer.disconnect();
  }, [onActivePageChange, pages, readerRef, readingMode]);
}
