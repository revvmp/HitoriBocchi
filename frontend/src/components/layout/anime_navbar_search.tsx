"use client";

import NavbarSearch, {
  type NavbarSearchConfig,
  type NavbarSearchEvent,
} from "@/components/layout/navbar_search";
import {
  getAnime,
  importAnime,
  streamAnimeSearch,
  type AnimeSearchEvent,
  type AnimeSummary,
} from "@/lib/api/anime";

function toNavbarSearchEvent(event: AnimeSearchEvent): NavbarSearchEvent<AnimeSummary> {
  return event.type === "anime"
    ? {
        item: event.anime,
        replaces_skeleton: event.replaces_skeleton,
        type: "item",
      }
    : event;
}

const animeSearchConfig: NavbarSearchConfig<AnimeSummary> = {
  detailPath: "/anime/",
  emptyMessage: "No anime found.",
  getLocalResults: (query, limit) =>
    getAnime("latest", query, limit).then((response) => response.animes),
  imageNoun: "poster",
  importErrorMessage: "Unable to add anime",
  importResult: (id) =>
    importAnime(id).then((response) => response.anime.slug),
  inputId: "navbar-search",
  inputLabel: "Search anime",
  placeholder: "Search anime...",
  renderDetails: (item) => (
    <>
      <span>
        <span aria-hidden="true">★ </span>
        {item.rating > 0 ? item.rating : "Not rated"}
      </span>
      <span>{item.status || "Unknown status"}</span>
      <span>
        {item.total_episodes || "?"} episodes
      </span>
    </>
  ),
  resultsHeading: "Top Anime results",
  resultsLabel: "Top MyAnimeList results",
  searchErrorMessage: "Unable to search anime",
  searchPath: "/search",
  skeletonKeyPrefix: "search-skeleton-",
  streamResults: (query, limit, onEvent, signal) =>
    streamAnimeSearch(
      query,
      limit,
      (event) => onEvent(toNavbarSearchEvent(event)),
      signal,
    ),
  submitLabel: "Search",
};

export default function AnimeNavbarSearch() {
  return <NavbarSearch config={animeSearchConfig} />;
}
