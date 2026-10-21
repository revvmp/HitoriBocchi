"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import * as adminRoutes from "@/components/admin/admin_routes";
import type { Pagination } from "@/lib/api/anime";

export const ADMIN_LIBRARY_PAGE_SIZE = 20;

type AdminLibraryItem = {
  slug: string;
  title: string;
  title_english: string;
};

type AdminActionResponse = {
  message: string;
};

export type AdminLibraryConfig<T extends AdminLibraryItem> = {
  clearPaginationOnError: boolean;
  deleteEmptyConfirmation: string;
  deleteEmptyErrorMessage: string;
  deleteEmptyItems: () => Promise<AdminActionResponse>;
  deleteErrorMessage: string;
  deleteItem: (slug: string) => Promise<AdminActionResponse>;
  getDeleteConfirmation: (title: string) => string;
  loadErrorMessage: string;
  loadPage: (
    limit: number,
    offset: number,
    searchQuery: string,
  ) => Promise<{ items: T[]; pagination: Pagination }>;
  routes: adminRoutes.AdminRoutes;
};

// Shared paginated search, delete, and bulk-delete state for the admin anime
// and manga libraries. The config must be a stable module-level constant.
export default function useAdminLibrary<T extends AdminLibraryItem>(config: AdminLibraryConfig<T>, refreshKey: number) {
  const router = useRouter();
  const [items, setItems] = useState<T[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [deletingSlug, setDeletingSlug] = useState<string | null>(null);
  const [isDeletingEmptyItems, setIsDeletingEmptyItems] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState<Pagination>({
    count: 0,
    has_more: false,
    limit: ADMIN_LIBRARY_PAGE_SIZE,
    offset: 0,
  });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let isActive = true;
    const offset = (page - 1) * ADMIN_LIBRARY_PAGE_SIZE;

    config.loadPage(ADMIN_LIBRARY_PAGE_SIZE, offset, searchQuery)
      .then((response) => {
        if (isActive) {
          setItems(response.items);
          setPagination(response.pagination);
          setErrorMessage("");
        }
      })
      .catch((error) => {
        if (!isActive) {
          return;
        }

        if (adminRoutes.redirectOnAdminAuthorizationError(error, router, config.routes)) {
          return;
        }

        setErrorMessage(
          error instanceof Error ? error.message : config.loadErrorMessage,
        );
        setItems([]);

        if (config.clearPaginationOnError) {
          setPagination({
            count: 0,
            has_more: false,
            limit: ADMIN_LIBRARY_PAGE_SIZE,
            offset,
          });
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [config, page, refreshKey, reloadKey, router, searchQuery]);

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nextSearchQuery = searchInput.trim();

    setErrorMessage("");
    setSuccessMessage("");
    setIsLoading(true);

    if (page === 1 && nextSearchQuery === searchQuery) {
      setReloadKey((current) => current + 1);
      return;
    }

    setPage(1);
    setSearchQuery(nextSearchQuery);
  }

  function handleClearSearch() {
    setSearchInput("");
    setErrorMessage("");
    setSuccessMessage("");
    setIsLoading(true);
    setPage(1);
    setSearchQuery("");
  }

  function handlePageChange(nextPage: number) {
    setErrorMessage("");
    setIsLoading(true);
    setPage(nextPage);
  }

  async function handleDelete(item: T) {
    const title = item.title_english || item.title;
    const confirmed = window.confirm(config.getDeleteConfirmation(title));

    if (!confirmed) {
      return;
    }

    setDeletingSlug(item.slug);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const response = await config.deleteItem(item.slug);

      setItems((current) =>
        current.filter((currentItem) => currentItem.slug !== item.slug),
      );
      setSuccessMessage(response.message);

      if (items.length === 1 && page > 1) {
        setIsLoading(true);
        setPage((current) => current - 1);
      } else {
        setReloadKey((current) => current + 1);
      }
    } catch (error) {
      if (adminRoutes.redirectOnAdminAuthorizationError(error, router, config.routes)) {
        return;
      }

      setErrorMessage(
        error instanceof Error ? error.message : config.deleteErrorMessage,
      );
    } finally {
      setDeletingSlug(null);
    }
  }

  async function handleDeleteEmptyItems() {
    const confirmed = window.confirm(config.deleteEmptyConfirmation);

    if (!confirmed) {
      return;
    }

    setIsDeletingEmptyItems(true);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const response = await config.deleteEmptyItems();

      setSuccessMessage(response.message);
      setIsLoading(true);
      setPage(1);
      setReloadKey((current) => current + 1);
    } catch (error) {
      if (adminRoutes.redirectOnAdminAuthorizationError(error, router, config.routes)) {
        return;
      }

      setErrorMessage(
        error instanceof Error
          ? error.message
          : config.deleteEmptyErrorMessage,
      );
    } finally {
      setIsDeletingEmptyItems(false);
    }
  }

  return {
    deletingSlug,
    errorMessage,
    handleClearSearch,
    handleDelete,
    handleDeleteEmptyItems,
    handlePageChange,
    handleSearch,
    isBusy: deletingSlug !== null || isDeletingEmptyItems,
    isDeletingEmptyItems,
    isLoading,
    items,
    page,
    pagination,
    searchInput,
    searchQuery,
    setSearchInput,
    successMessage,
  };
}
