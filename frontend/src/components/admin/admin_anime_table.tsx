"use client";

import * as adminRoutes from "@/components/admin/admin_routes";
import useAdminLibrary, { type AdminLibraryConfig } from "@/components/admin/use_admin_library";
import PaginationControls from "@/components/common/pagination_controls";
import {
  deleteAdminAnime,
  deleteAdminAnimesWithoutEpisodes,
  getAdminAnimes,
} from "@/lib/api/admin";
import type { AnimeSummary } from "@/lib/api/anime";

const animeLibraryConfig: AdminLibraryConfig<AnimeSummary> = {
  clearPaginationOnError: true,
  deleteEmptyConfirmation:
    "Delete all anime with no stored episodes? This cannot be undone.",
  deleteEmptyErrorMessage: "Unable to delete anime without episodes",
  deleteEmptyItems: deleteAdminAnimesWithoutEpisodes,
  deleteErrorMessage: "Unable to delete anime",
  deleteItem: deleteAdminAnime,
  getDeleteConfirmation: (title) =>
    `Delete ${title}? Its episodes, watch history, and comments will also be deleted. This cannot be undone.`,
  loadErrorMessage: "Unable to load anime",
  loadPage: (limit, offset, searchQuery) =>
    getAdminAnimes(limit, offset, searchQuery).then((response) => ({
      items: response.animes,
      pagination: response.pagination,
    })),
  routes: adminRoutes.ANIME_ADMIN_ROUTES,
};

type AdminAnimeTableProps = {
  refreshKey: number;
};

export default function AdminAnimeTable({
  refreshKey,
}: AdminAnimeTableProps) {
  const {
    deletingSlug,
    errorMessage,
    handleClearSearch,
    handleDelete,
    handleDeleteEmptyItems: handleDeleteWithoutEpisodes,
    handlePageChange,
    handleSearch,
    isBusy,
    isDeletingEmptyItems: isDeletingWithoutEpisodes,
    isLoading,
    items: animes,
    page,
    pagination,
    searchInput,
    searchQuery,
    setSearchInput,
    successMessage,
  } = useAdminLibrary(animeLibraryConfig, refreshKey);

  return (
    <section aria-labelledby="anime-management-title" className="mb-8">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2
            id="anime-management-title"
            className="text-lg font-semibold sm:text-xl"
          >
            Anime Library
          </h2>
          <p className="mt-1 text-sm text-home-muted">
            Review and remove anime currently stored in the database.
          </p>
        </div>
        <span className="shrink-0 text-sm text-home-muted">
          {pagination.count > 0
            ? `Showing ${pagination.offset + 1}-${pagination.offset + pagination.count} anime`
            : "0 anime"}
        </span>
      </div>

      <div className="mb-4 flex flex-col gap-2 lg:flex-row">
        <form
          className="flex max-w-xl flex-1 flex-col gap-2 sm:flex-row"
          onSubmit={handleSearch}
          role="search"
        >
          <label className="sr-only" htmlFor="admin-anime-search">
            Search anime library
          </label>
          <input
            className="h-10 min-w-0 flex-1 rounded-md border border-home-surface bg-home-background px-3 text-sm text-home-text outline-none transition placeholder:text-home-muted focus:border-home-accent"
            id="admin-anime-search"
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search by anime title"
            type="search"
            value={searchInput}
          />
          <div className="flex gap-2">
            <button
              className="h-10 flex-1 rounded-md bg-home-text px-4 text-sm font-semibold text-home-background transition hover:opacity-90 sm:flex-none"
              type="submit"
            >
              Search
            </button>
            {searchQuery && (
              <button
                className="h-10 flex-1 rounded-md border border-home-surface px-4 text-sm font-semibold text-home-muted transition hover:border-home-accent hover:text-home-text sm:flex-none"
                onClick={handleClearSearch}
                type="button"
              >
                Clear
              </button>
            )}
          </div>
        </form>
        <button
          className="h-10 rounded-md border border-home-danger/70 px-3 text-sm font-semibold text-home-muted transition hover:border-home-danger hover:bg-home-danger/5 hover:text-home-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-home-danger/70 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isBusy}
          onClick={handleDeleteWithoutEpisodes}
          type="button"
        >
          {isDeletingWithoutEpisodes
            ? "Deleting..."
            : "Delete all animes with 0 episodes"}
        </button>
      </div>

      {(successMessage || errorMessage) && (
        <p
          aria-live="polite"
          className={`mb-3 text-sm ${
            successMessage ? "text-home-accent" : "text-home-muted"
          }`}
        >
          {successMessage || errorMessage}
        </p>
      )}

      {isLoading ? (
        <p className="text-sm text-home-muted">Loading anime...</p>
      ) : animes.length === 0 ? (
        <>
          <p className="text-sm text-home-muted">
            {searchQuery
              ? `No anime found for "${searchQuery}".`
              : "No anime found."}
          </p>
          <PaginationControls
            disabled={isBusy}
            hasMore={pagination.has_more}
            onPageChange={handlePageChange}
            page={page}
          />
        </>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-home-surface">
            <table className="w-full min-w-4xl border-collapse text-left">
              <thead className="bg-home-surface/80 text-xs uppercase tracking-wide text-home-muted">
                <tr>
                  <th className="px-3 py-3 font-semibold">MAL ID</th>
                  <th className="px-3 py-3 font-semibold">Title</th>
                  <th className="px-3 py-3 font-semibold">Slug</th>
                  <th className="px-3 py-3 font-semibold">Status</th>
                  <th className="px-3 py-3 font-semibold">Episodes</th>
                  <th className="px-3 py-3 font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-home-surface">
                {animes.map((anime) => {
                  const title = anime.title_english || anime.title;
                  const isDeleting = deletingSlug === anime.slug;

                  return (
                    <tr className="bg-home-background" key={anime.id}>
                      <td className="px-3 py-4 text-sm text-home-muted">
                        {anime.id}
                      </td>
                      <td className="max-w-72 px-3 py-4 text-sm font-medium">
                        {title}
                      </td>
                      <td className="max-w-64 px-3 py-4 text-sm text-home-muted">
                        <span className="block truncate" title={anime.slug}>
                          {anime.slug}
                        </span>
                      </td>
                      <td className="px-3 py-4 text-sm whitespace-nowrap text-home-muted">
                        {anime.status || "Unknown"}
                      </td>
                      <td className="px-3 py-4 text-sm whitespace-nowrap text-home-muted">
                        {anime.current_episodes} / {anime.total_episodes || "?"}
                      </td>
                      <td className="px-3 py-4">
                        <button
                          className="h-10 rounded-md border border-home-danger/70 px-3 text-sm font-semibold text-home-muted transition hover:border-home-danger hover:bg-home-danger/5 hover:text-home-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-home-danger/70 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={isBusy}
                          onClick={() => handleDelete(anime)}
                          type="button"
                        >
                          {isDeleting ? "Deleting..." : "Delete"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <PaginationControls
            disabled={isBusy}
            hasMore={pagination.has_more}
            onPageChange={handlePageChange}
            page={page}
          />
        </>
      )}
    </section>
  );
}
