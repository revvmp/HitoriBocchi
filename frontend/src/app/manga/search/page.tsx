import type { Metadata } from "next";

import MangaListingPage from "@/components/manga/manga_listing_page";

export const metadata: Metadata = {
  title: "Manga Search - HitoriBocchi",
};

type MangaSearchPageProps = {
  searchParams: Promise<{ query?: string | string[] }>;
};

export default async function MangaSearchPage({
  searchParams,
}: MangaSearchPageProps) {
  const searchValue = (await searchParams).query;
  const query = Array.isArray(searchValue)
    ? searchValue[0]?.trim() ?? ""
    : searchValue?.trim() ?? "";

  if (!query) {
    return (
      <main className="min-h-svh bg-home-background px-4 py-5 text-home-text sm:px-6 sm:py-7 lg:px-8">
        <div className="mx-auto max-w-[120rem] rounded-md border border-dashed border-home-surface p-6 text-center">
          <p className="text-sm text-home-muted">
            Enter a manga or manhwa title in the search bar.
          </p>
        </div>
      </main>
    );
  }

  return (
    <MangaListingPage
      title={`Search results for ${query}`}
      view="latest"
      searchQuery={query}
    />
  );
}
