import type { Metadata } from "next";

import AnimeListingPage from "@/components/anime/anime_listing_page";

export const metadata: Metadata = {
    title: "Search - HitoriBocchi",
};

type SearchPageProps = {
    searchParams: Promise<{ query?: string | string[] }>;
};

export default async function SearchPage({ searchParams }: SearchPageProps) {
    const searchValue = (await searchParams).query;
    const query = Array.isArray(searchValue)
        ? searchValue[0]?.trim() ?? ""
        : searchValue?.trim() ?? "";

    if (!query) {
        return (
            <main className="min-h-svh bg-home-background px-4 py-5 text-home-text sm:px-6 sm:py-7 lg:px-8">
                <p className="text-sm text-home-muted">
                    Enter an anime title in the search bar.
                </p>
            </main>
        );
    }

    return (
        <AnimeListingPage
            title={`Search results for ${query}`}
            view="latest"
            searchQuery={query}
        />
    );
}
