"use client";

import { useCallback, useEffect, useState } from "react";

import * as readerSettings from "@/components/manga/reader/reader_settings";

// Persists the reading mode and zoom level in browser storage.
export default function useReaderPreferences() {
  const [readingMode, setReadingMode] =
    useState<readerSettings.ReadingMode>("top-down");
  const [zoomLevel, setZoomLevel] = useState(
    readerSettings.DEFAULT_READER_ZOOM,
  );

  useEffect(() => {
    const settingsTimeout = window.setTimeout(() => {
      try {
        const savedReadingMode = window.localStorage.getItem(
          readerSettings.MANGA_READING_MODE_KEY,
        );

        if (
          savedReadingMode === "right-to-left"
          || savedReadingMode === "top-down"
        ) {
          setReadingMode(savedReadingMode);
        }

        const savedZoom = Number.parseFloat(
          window.localStorage.getItem(readerSettings.MANGA_READER_ZOOM_KEY) || "",
        );

        if (Number.isFinite(savedZoom)) {
          setZoomLevel(readerSettings.normalizeZoom(savedZoom));
        }
      } catch {
        // The default reader settings remain when storage is blocked.
      }
    }, 0);

    return () => window.clearTimeout(settingsTimeout);
  }, []);

  const saveReadingMode = useCallback(
    (nextMode: readerSettings.ReadingMode) => {
      setReadingMode(nextMode);

      try {
        window.localStorage.setItem(
          readerSettings.MANGA_READING_MODE_KEY,
          nextMode,
        );
      } catch {
        // The selected mode still works for the current page without storage.
      }
    },
    [],
  );

  const handleZoomChange = useCallback((nextZoom: number) => {
    const normalizedZoom = readerSettings.normalizeZoom(nextZoom);
    setZoomLevel(normalizedZoom);

    try {
      window.localStorage.setItem(
        readerSettings.MANGA_READER_ZOOM_KEY,
        normalizedZoom.toFixed(1),
      );
    } catch {
      // Zoom still works for the current page without storage.
    }
  }, []);

  return {
    handleZoomChange,
    readingMode,
    saveReadingMode,
    zoomLevel,
  };
}
