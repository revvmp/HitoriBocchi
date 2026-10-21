"use client";

import { useCallback, useEffect, useState } from "react";

export default function useBrowserFullscreen() {
  const [isBrowserFullscreen, setIsBrowserFullscreen] = useState(false);
  const [canUseBrowserFullscreen, setCanUseBrowserFullscreen] = useState(false);

  useEffect(() => {
    function handleFullscreenChange() {
      setIsBrowserFullscreen(Boolean(document.fullscreenElement));
    }

    const capabilityTimeout = window.setTimeout(() => {
      setCanUseBrowserFullscreen(Boolean(
        document.documentElement.requestFullscreen,
      ));
      handleFullscreenChange();
    }, 0);
    document.addEventListener("fullscreenchange", handleFullscreenChange);

    return () => {
      window.clearTimeout(capabilityTimeout);
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  const toggleBrowserFullscreen = useCallback(async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await document.documentElement.requestFullscreen();
      }
    } catch {
      // The browser can deny fullscreen even after a user gesture.
    }
  }, []);

  // Navigation away from the reader should not leave the browser in fullscreen.
  const leaveReaderFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      return;
    }

    void document.exitFullscreen().catch(() => {
      // Navigation should continue if the browser refuses to exit fullscreen.
    });
  }, []);

  return {
    canUseBrowserFullscreen,
    isBrowserFullscreen,
    leaveReaderFullscreen,
    toggleBrowserFullscreen,
  };
}
