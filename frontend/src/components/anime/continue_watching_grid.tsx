"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import AnimeCard from "@/components/anime/anime_card";
import CatalogGridSkeleton, { CATALOG_GRID_CLASS_NAME } from "@/components/common/catalog_grid_skeleton";
import PaginationControls from "@/components/common/pagination_controls";
import {
  getOptionalCurrentUser,
  getSiteSettings,
} from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import {
  clearWatchHistory,
  getWatchHistorySettings,
  getWatchHistory,
  updateWatchHistoryTracking,
  type WatchHistory,
} from "@/lib/api/watch_history";

const pageSize = 36;
const gridClassName = "anime-grid " + CATALOG_GRID_CLASS_NAME;

export default function ContinueWatchingGrid() {
  const router = useRouter();
  const [watchHistory, setWatchHistory] = useState<WatchHistory[]>([]);
  const [actionError, setActionError] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingTracking, setIsSavingTracking] = useState(false);
  const [isTrackingEnabled, setIsTrackingEnabled] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    let isActive = true;

    async function loadWatchHistory() {
      try {
        const [settings, currentUser] = await Promise.all([
          getSiteSettings(),
          getOptionalCurrentUser(),
        ]);

        if (!isActive) {
          return;
        }

        if (!currentUser) {
          if (settings.login_required) {
            router.replace("/login");
          } else {
            setIsAnonymous(true);
          }
          return;
        }

        setIsAuthenticated(true);
        const [response, trackingSettings] = await Promise.all([
          getWatchHistory(pageSize, (page - 1) * pageSize),
          getWatchHistorySettings(),
        ]);

        if (isActive) {
          setWatchHistory(response.watch_history);
          setHasMore(response.pagination.has_more);
          setIsTrackingEnabled(trackingSettings.tracking_enabled);
        }
      } catch (error) {
        if (!isActive) {
          return;
        }

        if (error instanceof ApiError && [401, 403].includes(error.status)) {
          router.replace("/login");
          return;
        }

        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Unable to load watch history",
        );
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    loadWatchHistory();

    return () => {
      isActive = false;
    };
  }, [page, router]);

  function handlePageChange(nextPage: number) {
    setActionError("");
    setErrorMessage("");
    setIsLoading(true);
    setPage(nextPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleClearHistory() {
    if (watchHistory.length === 0) {
      return;
    }

    if (!window.confirm("Clear your entire watch history? This cannot be undone.")) {
      return;
    }

    setActionError("");
    setIsClearing(true);

    try {
      await clearWatchHistory();
      setWatchHistory([]);
      setHasMore(false);
      setPage(1);
    } catch (error) {
      if (error instanceof ApiError && [401, 403].includes(error.status)) {
        router.replace("/login");
        return;
      }

      setActionError(
        error instanceof Error
          ? error.message
          : "Unable to clear watch history",
      );
    } finally {
      setIsClearing(false);
    }
  }

  async function handleTrackingToggle() {
    const nextTrackingEnabled = !isTrackingEnabled;

    setActionError("");
    setIsSavingTracking(true);

    try {
      const settings = await updateWatchHistoryTracking(
        nextTrackingEnabled,
      );
      setIsTrackingEnabled(settings.tracking_enabled);
    } catch (error) {
      if (error instanceof ApiError && [401, 403].includes(error.status)) {
        router.replace("/login");
        return;
      }

      setActionError(
        error instanceof Error
          ? error.message
          : "Unable to update watch history tracking",
      );
    } finally {
      setIsSavingTracking(false);
    }
  }

  let content: ReactNode;

  if (isLoading) {
    content = (
      <CatalogGridSkeleton
        className={gridClassName}
        label="Loading watch history"
      />
    );
  } else if (isAnonymous) {
    content = (
      <p className="text-sm text-home-muted">
        Watch history is only saved for signed-in accounts.
      </p>
    );
  } else if (errorMessage) {
    content = (
      <>
        <p className="text-sm text-home-muted">{errorMessage}</p>
        <PaginationControls
          hasMore={false}
          onPageChange={handlePageChange}
          page={page}
        />
      </>
    );
  } else if (watchHistory.length === 0) {
    content = (
      <>
        <p className="text-sm text-home-muted">
          Episodes you start watching will appear here.
        </p>
        <PaginationControls
          hasMore={hasMore}
          onPageChange={handlePageChange}
          page={page}
        />
      </>
    );
  } else {
    content = (
      <>
        <div className={gridClassName}>
          {watchHistory.map((history) => {
            const progress =
              history.duration_seconds > 0
                ? (history.current_time_seconds / history.duration_seconds) * 100
                : 0;

            return (
              <AnimeCard
                anime={history.anime}
                episodeNumber={history.episode_number}
                href={
                  "/watch/" + history.anime_slug
                  + "/episode/" + history.episode_number
                }
                key={history.episode_id}
                progress={progress}
              />
            );
          })}
        </div>

        <PaginationControls
          hasMore={hasMore}
          onPageChange={handlePageChange}
          page={page}
        />
      </>
    );
  }

  return (
    <>
      <header className="mb-5 flex flex-col gap-3 border-b border-home-surface pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-[1.375rem] font-semibold tracking-tight sm:text-[1.625rem]">
            Continue Watching
          </h1>
        </div>

        {isAuthenticated && (
          <div className="flex flex-wrap gap-2">
            <button
              aria-checked={isTrackingEnabled}
              className={
                "rounded-md border px-3 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 "
                + (isTrackingEnabled
                  ? "border-home-accent bg-home-accent text-home-background"
                  : "border-home-accent/60 text-home-muted hover:border-home-accent hover:text-home-text")
              }
              disabled={isSavingTracking}
              onClick={handleTrackingToggle}
              role="switch"
              type="button"
            >
              {isSavingTracking
                ? "Saving..."
                : "Tracking: " + (isTrackingEnabled ? "On" : "Off")}
            </button>

            <button
              aria-label="Clear watch history"
              className="rounded-md border border-home-accent/60 px-3 py-2 text-sm font-semibold text-home-muted transition hover:border-home-accent hover:text-home-text disabled:cursor-not-allowed disabled:opacity-60 sm:px-4"
              disabled={isClearing}
              onClick={handleClearHistory}
              type="button"
            >
              {isClearing ? "Clearing..." : "Clear watch history"}
            </button>
          </div>
        )}
      </header>

      {actionError && (
        <p aria-live="polite" className="mb-4 text-sm text-home-muted">
          {actionError}
        </p>
      )}

      {content}
    </>
  );
}
