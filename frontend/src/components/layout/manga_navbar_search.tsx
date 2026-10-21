"use client";

import NavbarSearch, {
  type NavbarSearchConfig,
  type NavbarSearchEvent,
} from "@/components/layout/navbar_search";
import {
  getManga,
  importManga,
  streamMangaSearch,
  type MangaSearchEvent,
  type MangaSummary,
} from "@/lib/api/manga";

function toNavbarSearchEvent(event: MangaSearchEvent): NavbarSearchEvent<MangaSummary> {
  return event.type === "manga"
    ? {
        item: event.manga,
        replaces_skeleton: event.replaces_skeleton,
        type: "item",
      }
    : event;
}

const mangaSearchConfig: NavbarSearchConfig<MangaSummary> = {
  detailPath: "/manga/",
  emptyMessage: "No manga found.",
  getLocalResults: (query, limit) =>
    getManga("latest", query, limit).then((response) => response.mangas),
  imageNoun: "cover",
  importErrorMessage: "Unable to add manga",
  importResult: (id) =>
    importManga(id).then((response) => response.manga.slug),
  inputId: "manga-navbar-search",
  inputLabel: "Search manga and manhwa",
  placeholder: "Search manga...",
  renderDetails: (item) => (
    <>
      <span>
        <span aria-hidden="true">★ </span>
        {item.rating > 0 ? item.rating : "Not rated"}
      </span>
      <span>{item.media_type || "Manga"}</span>
      <span>{item.total_chapters || "?"} chapters</span>
    </>
  ),
  resultsHeading: "Top Manga results",
  resultsLabel: "Top MyAnimeList manga results",
  searchErrorMessage: "Unable to search manga",
  searchPath: "/manga/search",
  skeletonKeyPrefix: "manga-search-skeleton-",
  streamResults: (query, limit, onEvent, signal) =>
    streamMangaSearch(
      query,
      limit,
      (event) => onEvent(toNavbarSearchEvent(event)),
      signal,
    ),
  submitLabel: "Search manga",
};

export default function MangaNavbarSearch() {
  return <NavbarSearch config={mangaSearchConfig} />;
}
