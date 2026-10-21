import type { Metadata } from "next";

import AnimeListingPage from "@/components/anime/anime_listing_page";

export const metadata: Metadata = {
    title: "HitoriBocchi",
    description: "Recently updated anime on HitoriBocchi.",
};

export default function Home() {
    return <AnimeListingPage title="Latest Episodes" view="latest" />;
}
