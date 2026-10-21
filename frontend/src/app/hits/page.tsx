import type { Metadata } from "next";

import AnimeListingPage from "@/components/anime/anime_listing_page";

export const metadata: Metadata = {
    title: "Hits - HitoriBocchi",
};

export default function HitsPage() {
    return <AnimeListingPage title="Top Hits" view="hits" />;
}
