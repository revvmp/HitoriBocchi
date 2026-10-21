"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api/client";

export const CATALOG_PAGE_SIZE = 36;

export type CatalogPage<T> = {
  hasMore: boolean;
  items: T[];
};

// The loader must be memoized because a new loader reloads the current page.
export type CatalogPageLoader<T> = (
  limit: number,
  offset: number,
) => Promise<CatalogPage<T>>;

export default function usePaginatedCatalog<T>(loadPage: CatalogPageLoader<T>, loginPath: string, fallbackErrorMessage: string) {
  const router = useRouter();
  const [items, setItems] = useState<T[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    let isActive = true;

    async function loadItems() {
      try {
        const response = await loadPage(
          CATALOG_PAGE_SIZE,
          (page - 1) * CATALOG_PAGE_SIZE,
        );

        if (!isActive) {
          return;
        }

        setItems(response.items);
        setHasMore(response.hasMore);
        setErrorMessage("");
      } catch (error) {
        if (!isActive) {
          return;
        }

        if (error instanceof ApiError && [401, 403].includes(error.status)) {
          router.replace(loginPath);
          return;
        }

        setErrorMessage(
          error instanceof Error ? error.message : fallbackErrorMessage,
        );
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    loadItems();

    return () => {
      isActive = false;
    };
  }, [fallbackErrorMessage, loadPage, loginPath, page, router]);

  function handlePageChange(nextPage: number) {
    setErrorMessage("");
    setIsLoading(true);
    setPage(nextPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return {
    errorMessage,
    handlePageChange,
    hasMore,
    isLoading,
    items,
    page,
  };
}
