import type { Metadata } from "next";

import AnimeListingPage from "@/components/anime/anime_listing_page";

export const metadata: Metadata = {
    title: "Popular - HitoriBocchi",
};

export default function PopularPage() {
    return <AnimeListingPage title="Popular Animes" view="popular" />;
}
