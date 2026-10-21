"use client";

import Link from "next/link";

import * as adminRoutes from "@/components/admin/admin_routes";
import useAdminLibrary, { type AdminLibraryConfig } from "@/components/admin/use_admin_library";
import PaginationControls from "@/components/common/pagination_controls";
import {
  deleteAdminManga,
  deleteAdminMangasWithoutChapters,
  getAdminMangas,
} from "@/lib/api/admin";
import type { MangaSummary } from "@/lib/api/manga";

const mangaLibraryConfig: AdminLibraryConfig<MangaSummary> = {
  clearPaginationOnError: false,
  deleteEmptyConfirmation:
    "Delete all manga with no stored chapters? User bookmarks for those titles will also be deleted. This cannot be undone.",
  deleteEmptyErrorMessage: "Unable to delete manga without chapters",
  deleteEmptyItems: deleteAdminMangasWithoutChapters,
  deleteErrorMessage: "Unable to delete manga",
  deleteItem: deleteAdminManga,
  getDeleteConfirmation: (title) =>
    `Delete ${title}? Its chapters and user bookmarks will also be deleted. This cannot be undone.`,
  loadErrorMessage: "Unable to load manga",
  loadPage: (limit, offset, searchQuery) =>
    getAdminMangas(limit, offset, searchQuery).then((response) => ({
      items: response.mangas,
      pagination: response.pagination,
    })),
  routes: adminRoutes.MANGA_ADMIN_ROUTES,
};

type AdminMangaTableProps = {
  refreshKey: number;
};

export default function AdminMangaTable({
  refreshKey,
}: AdminMangaTableProps) {
  const {
    deletingSlug,
    errorMessage,
    handleClearSearch,
    handleDelete,
    handleDeleteEmptyItems: handleDeleteWithoutChapters,
    handlePageChange,
    handleSearch,
    isBusy,
    isDeletingEmptyItems: isDeletingWithoutChapters,
    isLoading,
    items: mangas,
    page,
    pagination,
    searchInput,
    searchQuery,
    setSearchInput,
    successMessage,
  } = useAdminLibrary(mangaLibraryConfig, refreshKey);

  return (
    <section aria-labelledby="manga-management-title" className="mb-8">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2
            id="manga-management-title"
            className="text-lg font-semibold sm:text-xl"
          >
            Manga Library
          </h2>
          <p className="mt-1 text-sm text-home-muted">
            Review and remove manga stored in the database.
          </p>
        </div>
        <span className="shrink-0 text-sm text-home-muted">
          {pagination.count > 0
            ? `Showing ${pagination.offset + 1}-${pagination.offset + pagination.count}`
            : "0 manga"}
        </span>
      </div>

      <div className="mb-4 flex flex-col gap-2 lg:flex-row">
        <form
          className="flex max-w-xl flex-1 flex-col gap-2 sm:flex-row"
          onSubmit={handleSearch}
          role="search"
        >
          <label className="sr-only" htmlFor="admin-manga-search">
            Search manga library
          </label>
          <input
            className="h-10 min-w-0 flex-1 rounded-md border border-home-surface bg-home-background px-3 text-sm text-home-text outline-none transition placeholder:text-home-muted focus:border-home-accent"
            id="admin-manga-search"
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search by manga title"
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
          className="h-10 rounded-md border border-home-danger/70 px-3 text-sm font-semibold text-home-muted transition hover:border-home-danger hover:bg-home-danger/5 hover:text-home-text disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isBusy}
          onClick={handleDeleteWithoutChapters}
          type="button"
        >
          {isDeletingWithoutChapters
            ? "Deleting..."
            : "Delete manga with 0 chapters"}
        </button>
      </div>

      {(successMessage || errorMessage) && (
        <p
          aria-live="polite"
          className={`mb-3 rounded-md border border-home-surface bg-home-surface/30 p-3 text-sm ${
            successMessage ? "text-home-accent" : "text-home-muted"
          }`}
        >
          {successMessage || errorMessage}
        </p>
      )}

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Loading manga library">
          {Array.from({ length: 6 }, (_, index) => (
            <div className="h-36 animate-pulse rounded-lg bg-home-surface" key={index} />
          ))}
        </div>
      ) : mangas.length === 0 ? (
        <p className="text-sm text-home-muted">
          {searchQuery ? `No manga found for “${searchQuery}”.` : "No manga found."}
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {mangas.map((manga) => {
            const title = manga.title_english || manga.title;
            const isDeleting = deletingSlug === manga.slug;

            return (
              <article
                className="rounded-lg border border-home-surface bg-home-surface/20 p-4"
                key={manga.id}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate font-semibold" title={title}>
                      {title}
                    </h3>
                    <p className="mt-1 truncate text-xs text-home-muted" title={manga.slug}>
                      {manga.slug}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-sm bg-home-surface px-2 py-1 text-[10px] font-semibold uppercase text-home-muted">
                    {manga.media_type || "Manga"}
                  </span>
                </div>
                <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <dt className="text-home-muted">MAL ID</dt>
                    <dd className="mt-0.5 font-semibold">{manga.id}</dd>
                  </div>
                  <div>
                    <dt className="text-home-muted">Status</dt>
                    <dd className="mt-0.5 truncate font-semibold">
                      {manga.status || "Unknown"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-home-muted">Chapters</dt>
                    <dd className="mt-0.5 font-semibold">
                      {manga.current_chapters} / {manga.total_chapters || "?"}
                    </dd>
                  </div>
                </dl>
                <div className="mt-4 flex gap-2">
                  <Link
                    className="flex h-10 flex-1 items-center justify-center rounded-md border border-home-surface text-sm font-semibold text-home-muted transition hover:border-home-accent hover:text-home-text"
                    href={`/manga/${manga.slug}`}
                  >
                    View
                  </Link>
                  <button
                    className="h-10 flex-1 rounded-md border border-home-danger/70 text-sm font-semibold text-home-muted transition hover:border-home-danger hover:bg-home-danger/5 hover:text-home-text disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={isBusy}
                    onClick={() => handleDelete(manga)}
                    type="button"
                  >
                    {isDeleting ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <PaginationControls
        disabled={isBusy}
        hasMore={pagination.has_more}
        onPageChange={handlePageChange}
        page={page}
      />
    </section>
  );
}
