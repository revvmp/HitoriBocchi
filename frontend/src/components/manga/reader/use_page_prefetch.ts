"use client";

import { useCallback, useEffect, useRef } from "react";

import { MANGA_PAGE_PREFETCH_COUNT } from "@/components/manga/reader/reader_settings";
import type { MangaPage } from "@/lib/api/manga";

// Prefetches only the next few pages at low priority. Returns a function that
// forgets earlier prefetches when a different chapter loads.
export default function usePagePrefetch(pages: MangaPage[], activePageIndex: number) {
  const pendingPagePrefetchesRef = useRef<Map<string, HTMLImageElement>>(new Map());
  const prefetchedPageUrlsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const nextPages = pages.slice(
      activePageIndex + 1,
      activePageIndex + 1 + MANGA_PAGE_PREFETCH_COUNT,
    );

    for (const page of nextPages) {
      if (prefetchedPageUrlsRef.current.has(page.image_url)) {
        continue;
      }

      const prefetchedImage = new window.Image();
      prefetchedImage.decoding = "async";
      prefetchedImage.fetchPriority = "low";
      prefetchedImage.onload = () => {
        pendingPagePrefetchesRef.current.delete(page.image_url);
      };
      prefetchedImage.onerror = () => {
        pendingPagePrefetchesRef.current.delete(page.image_url);
        prefetchedPageUrlsRef.current.delete(page.image_url);
      };
      prefetchedPageUrlsRef.current.add(page.image_url);
      pendingPagePrefetchesRef.current.set(page.image_url, prefetchedImage);
      prefetchedImage.src = page.image_url;
    }
  }, [activePageIndex, pages]);

  useEffect(() => () => {
    for (const prefetchedImage of pendingPagePrefetchesRef.current.values()) {
      prefetchedImage.onload = null;
      prefetchedImage.onerror = null;
    }

    pendingPagePrefetchesRef.current.clear();
    prefetchedPageUrlsRef.current.clear();
  }, []);

  return useCallback(() => {
    pendingPagePrefetchesRef.current.clear();
    prefetchedPageUrlsRef.current.clear();
  }, []);
}
