"use client";

import { useCallback } from "react";

import AnimeCard from "@/components/anime/anime_card";
import CatalogGridSkeleton, { CATALOG_GRID_CLASS_NAME } from "@/components/common/catalog_grid_skeleton";
import PaginationControls from "@/components/common/pagination_controls";
import usePaginatedCatalog from "@/components/common/use_paginated_catalog";
import { getAnime, type AnimeView } from "@/lib/api/anime";

const gridClassName = "anime-grid " + CATALOG_GRID_CLASS_NAME;

type AnimeGridProps = {
  searchQuery?: string;
  view: AnimeView;
};

export default function AnimeGrid({ searchQuery, view }: AnimeGridProps) {
  const linksToLatestEpisode = view === "latest" && !searchQuery;
  const loadAnimePage = useCallback(
    (limit: number, offset: number) =>
      getAnime(view, searchQuery, limit, offset).then((response) => ({
        hasMore: response.pagination.has_more,
        items: response.animes,
      })),
    [searchQuery, view],
  );
  const {
    errorMessage,
    handlePageChange,
    hasMore,
    isLoading,
    items: anime,
    page,
  } = usePaginatedCatalog(loadAnimePage, "/login", "Unable to load anime");

  if (isLoading) {
    return (
      <CatalogGridSkeleton className={gridClassName} label="Loading anime" />
    );
  }

  if (errorMessage) {
    return (
      <>
        <p className="text-sm text-home-muted">{errorMessage}</p>
        <PaginationControls
          hasMore={false}
          onPageChange={handlePageChange}
          page={page}
        />
      </>
    );
  }

  if (anime.length === 0) {
    return (
      <>
        <p className="text-sm text-home-muted">No anime found.</p>
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
        {anime.map((item) => {
          const episodeNumber = linksToLatestEpisode
            ? item.latest_episode_number
            : 0;
          const episodeHref = episodeNumber > 0
            ? "/watch/" + item.slug + "/episode/" + episodeNumber
            : undefined;

          return (
            <AnimeCard
              anime={item}
              episodeNumber={episodeNumber || undefined}
              href={episodeHref}
              key={item.id}
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
