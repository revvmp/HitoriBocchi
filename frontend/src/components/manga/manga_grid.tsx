"use client";

import { useCallback } from "react";

import CatalogGridSkeleton, { CATALOG_GRID_CLASS_NAME } from "@/components/common/catalog_grid_skeleton";
import PaginationControls from "@/components/common/pagination_controls";
import usePaginatedCatalog from "@/components/common/use_paginated_catalog";
import MangaCard from "@/components/manga/manga_card";
import { getManga, type MangaView } from "@/lib/api/manga";

const gridClassName = "manga-grid " + CATALOG_GRID_CLASS_NAME;

type MangaGridProps = {
  searchQuery?: string;
  view: MangaView;
};

export default function MangaGrid({ searchQuery, view }: MangaGridProps) {
  const displaysLatestChapter = view === "latest" && !searchQuery;
  const loadMangaPage = useCallback(
    (limit: number, offset: number) =>
      getManga(view, searchQuery, limit, offset).then((response) => ({
        hasMore: response.pagination.has_more,
        items: response.mangas,
      })),
    [searchQuery, view],
  );
  const {
    errorMessage,
    handlePageChange,
    hasMore,
    isLoading,
    items: manga,
    page,
  } = usePaginatedCatalog(
    loadMangaPage,
    view === "bookmarks" ? "/login?next=/manga/bookmarks" : "/login",
    "Unable to load manga",
  );

  if (isLoading) {
    return (
      <CatalogGridSkeleton className={gridClassName} label="Loading manga" />
    );
  }

  if (errorMessage) {
    return (
      <>
        <div
          className="rounded-md border border-home-surface bg-home-surface/30 p-4"
          role="status"
        >
          <p className="text-sm text-home-muted">{errorMessage}</p>
        </div>
        <PaginationControls
          hasMore={false}
          onPageChange={handlePageChange}
          page={page}
        />
      </>
    );
  }

  if (manga.length === 0) {
    return (
      <>
        <div className="rounded-md border border-dashed border-home-surface p-6 text-center">
          <svg
            aria-hidden="true"
            className="mx-auto size-8 text-home-muted"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.5"
            viewBox="0 0 24 24"
          >
            <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5z" />
            <path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z" />
          </svg>
          <p className="mt-2 text-sm text-home-muted">
            {view === "bookmarks"
              ? "Your manga bookmarks will appear here."
              : "No manga found."}
          </p>
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
      <div className={gridClassName}>
        {manga.map((item) => {
          const chapterNumber = displaysLatestChapter
            ? item.latest_chapter_number
            : "";

          return (
            <MangaCard
              chapterNumber={chapterNumber || undefined}
              key={item.id}
              manga={item}
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
