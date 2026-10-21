"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type ReactNode,
} from "react";

import { ApiError } from "@/lib/api/client";

const searchResultLimit = 10;

export type NavbarSearchItem = {
  id: number;
  image: string;
  requires_import?: boolean;
  slug: string;
  synopsis: string;
  title: string;
  title_english: string;
};

export type NavbarSearchEvent<T> =
  | { type: "start"; total: number }
  | {
      type: "item";
      item: T;
      replaces_skeleton: boolean;
    }
  | {
      type: "error";
      message: string;
      replaces_skeleton?: boolean;
    }
  | { type: "complete" };

export type NavbarSearchConfig<T extends NavbarSearchItem> = {
  detailPath: string;
  emptyMessage: string;
  getLocalResults: (query: string, limit: number) => Promise<T[]>;
  imageNoun: string;
  importErrorMessage: string;
  importResult: (id: number) => Promise<string>;
  inputId: string;
  inputLabel: string;
  placeholder: string;
  renderDetails: (item: T) => ReactNode;
  resultsHeading: string;
  resultsLabel: string;
  searchErrorMessage: string;
  searchPath: string;
  skeletonKeyPrefix: string;
  streamResults: (
    query: string,
    limit: number,
    onEvent: (event: NavbarSearchEvent<T>) => void,
    signal: AbortSignal,
  ) => Promise<void>;
  submitLabel: string;
};

type NavbarSearchProps<T extends NavbarSearchItem> = {
  config: NavbarSearchConfig<T>;
};

// Shows matching local titles immediately, then streams transient
// MyAnimeList results into the same list. Selecting a transient result
// imports its metadata before navigating to the saved detail page.
export default function NavbarSearch<T extends NavbarSearchItem>({
  config,
}: NavbarSearchProps<T>) {
  const router = useRouter();
  const searchRef = useRef<HTMLDivElement>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [hasCompleted, setHasCompleted] = useState(false);
  const [importingItemId, setImportingItemId] = useState<number | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [localItems, setLocalItems] = useState<T[]>([]);
  const [malItems, setMalItems] = useState<T[]>([]);
  const [query, setQuery] = useState("");
  const [skeletonCount, setSkeletonCount] = useState(0);
  const normalizedQuery = query.trim();
  const showResults = isOpen && normalizedQuery.length >= 2;
  const searchHref =
    config.searchPath + "?query=" + encodeURIComponent(normalizedQuery);
  const resultsId = config.inputId + "-results";
  const items = [
    ...malItems,
    ...localItems.filter(
      (localItem) => !malItems.some((malItem) => malItem.id === localItem.id),
    ),
  ].slice(0, searchResultLimit);
  const visibleSkeletonCount = Math.min(
    skeletonCount,
    searchResultLimit - items.length,
  );

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (
        searchRef.current &&
        !searchRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, []);

  useEffect(() => {
    if (normalizedQuery.length < 2) {
      return;
    }

    let isActive = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      config.getLocalResults(normalizedQuery, searchResultLimit)
        .then((results) => {
          if (isActive) {
            setLocalItems(results);
          }
        })
        .catch((error) => {
          if (
            isActive &&
            error instanceof ApiError &&
            [401, 403].includes(error.status)
          ) {
            router.replace("/login");
          }
        });

      config.streamResults(
        normalizedQuery,
        searchResultLimit,
        (event) => {
          if (!isActive) {
            return;
          }

          if (event.type === "start") {
            setSkeletonCount(event.total);
          }

          if (event.type === "item") {
            setMalItems((currentItems) => (
              currentItems.some((item) => item.id === event.item.id)
                ? currentItems
                : [...currentItems, event.item]
            ));

            if (event.replaces_skeleton) {
              setSkeletonCount((count) => Math.max(0, count - 1));
            }
          }

          if (event.type === "error") {
            setErrorMessage(event.message);

            if (event.replaces_skeleton) {
              setSkeletonCount((count) => Math.max(0, count - 1));
            }
          }

          if (event.type === "complete") {
            setHasCompleted(true);
            setSkeletonCount(0);
          }
        },
        controller.signal,
      ).catch((error) => {
        if (!isActive || controller.signal.aborted) {
          return;
        }

        if (error instanceof ApiError && [401, 403].includes(error.status)) {
          router.replace("/login");
          return;
        }

        setErrorMessage(
          error instanceof Error ? error.message : config.searchErrorMessage,
        );
        setHasCompleted(true);
        setSkeletonCount(0);
      });
    }, 300);

    return () => {
      isActive = false;
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [config, normalizedQuery, router]);

  function handleQueryChange(event: ChangeEvent<HTMLInputElement>) {
    const nextQuery = event.target.value;
    const nextNormalizedQuery = nextQuery.trim();
    const hasSearchQuery = nextNormalizedQuery.length >= 2;

    if (nextNormalizedQuery !== normalizedQuery) {
      setErrorMessage("");
      setHasCompleted(false);
      setLocalItems([]);
      setMalItems([]);
      setSkeletonCount(hasSearchQuery ? 5 : 0);
    }

    setIsOpen(hasSearchQuery);
    setQuery(nextQuery);
  }

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!normalizedQuery) {
      return;
    }

    setIsOpen(true);
    router.push(searchHref);
  }

  async function handleImport(item: T) {
    if (importingItemId !== null) {
      return;
    }

    setErrorMessage("");
    setImportingItemId(item.id);

    try {
      const slug = await config.importResult(item.id);
      setIsOpen(false);
      router.push(config.detailPath + slug);
    } catch (error) {
      if (error instanceof ApiError && [401, 403].includes(error.status)) {
        router.replace("/login");
        return;
      }

      setErrorMessage(
        error instanceof Error ? error.message : config.importErrorMessage,
      );
    } finally {
      setImportingItemId(null);
    }
  }

  return (
    <div
      className="relative col-start-3 row-start-1 min-w-0 sm:mr-3 sm:w-52 sm:flex-none lg:w-64"
      ref={searchRef}
    >
      <form
        className="flex h-10 w-full overflow-hidden rounded-md border border-home-surface bg-home-surface/60 focus-within:border-home-accent"
        role="search"
        onSubmit={handleSearch}
      >
        <label className="sr-only" htmlFor={config.inputId}>
          {config.inputLabel}
        </label>
        <input
          aria-autocomplete="list"
          aria-controls={resultsId}
          aria-expanded={showResults}
          autoComplete="off"
          className="min-w-0 flex-1 bg-transparent px-3 text-base text-home-text outline-none placeholder:text-home-muted"
          id={config.inputId}
          name="query"
          onChange={handleQueryChange}
          onFocus={() => setIsOpen(normalizedQuery.length >= 2)}
          placeholder={config.placeholder}
          role="combobox"
          spellCheck={false}
          type="search"
          value={query}
        />
        <button
          type="submit"
          aria-label={config.submitLabel}
          className="flex size-10 shrink-0 items-center justify-center text-home-muted transition hover:text-home-text"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            className="size-5"
          >
            <circle cx="8.5" cy="8.5" r="5.5" />
            <path d="m13 13 4 4" />
          </svg>
        </button>
      </form>

      {showResults && (
        <div
          className="fixed left-4 right-4 top-[3.75rem] z-[60] w-auto overflow-hidden rounded-md border border-home-surface bg-home-background shadow-2xl sm:absolute sm:left-auto sm:right-0 sm:top-[calc(100%+0.5rem)] sm:w-[28rem] lg:w-[32rem]"
          id={resultsId}
          role="listbox"
          aria-label={config.resultsLabel}
        >
          <div className="border-b border-home-surface px-3 py-2 text-xs font-semibold uppercase tracking-wide text-home-muted">
            {config.resultsHeading}
          </div>

          <div className="max-h-[70vh] overflow-y-auto overscroll-contain sm:max-h-[32rem]">
            {items.map((item) => {
              const title = item.title_english || item.title;
              const hasPoster = item.image?.startsWith(
                "https://cdn.myanimelist.net/images/",
              );

              return (
                <Link
                  aria-busy={importingItemId === item.id}
                  aria-selected={false}
                  className={`flex min-w-0 gap-3 border-b border-home-surface/70 p-3 outline-none transition last:border-b-0 hover:bg-home-surface/60 focus-visible:bg-home-surface focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-home-accent ${
                    importingItemId === item.id ? "cursor-wait opacity-70" : ""
                  }`}
                  href={
                    item.requires_import
                      ? searchHref
                      : config.detailPath + item.slug
                  }
                  key={item.id}
                  onClick={(event) => {
                    if (item.requires_import) {
                      event.preventDefault();
                      handleImport(item);
                      return;
                    }

                    setIsOpen(false);
                  }}
                  prefetch={!item.requires_import}
                  role="option"
                >
                  <div className="relative h-16 w-12 shrink-0 overflow-hidden rounded-sm bg-home-surface">
                    {hasPoster ? (
                      <Image
                        alt={title + " " + config.imageNoun}
                        className="object-cover"
                        fill
                        sizes="3rem"
                        src={item.image}
                      />
                    ) : (
                      <div className="flex size-full items-center justify-center px-1 text-center text-[9px] text-home-muted">
                        No {config.imageNoun}
                      </div>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <h2
                      className="truncate text-sm font-medium text-home-text sm:text-base"
                      title={title}
                    >
                      {title}
                    </h2>
                    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-home-muted">
                      {config.renderDetails(item)}
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs leading-4 text-home-muted">
                      {item.synopsis || "No synopsis available."}
                    </p>
                  </div>
                </Link>
              );
            })}

            {Array.from({ length: visibleSkeletonCount }, (_, index) => (
              <div
                className="flex animate-pulse gap-3 border-b border-home-surface/70 p-3 last:border-b-0"
                key={config.skeletonKeyPrefix + index}
              >
                <div className="h-16 w-12 shrink-0 rounded-sm bg-home-surface" />
                <div className="min-w-0 flex-1 py-1">
                  <div className="h-4 w-4/5 rounded bg-home-surface" />
                  <div className="mt-2 h-3 w-2/3 rounded bg-home-surface" />
                  <div className="mt-2 h-3 w-full rounded bg-home-surface" />
                </div>
              </div>
            ))}

            {errorMessage && skeletonCount === 0 && (
              <p className="px-3 py-4 text-sm text-home-muted">
                {errorMessage}
              </p>
            )}

            {hasCompleted &&
              items.length === 0 &&
              !errorMessage &&
              skeletonCount === 0 && (
                <p className="px-3 py-4 text-sm text-home-muted">
                  {config.emptyMessage}
                </p>
              )}
          </div>
        </div>
      )}
    </div>
  );
}
