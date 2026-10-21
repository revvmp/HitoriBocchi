import type { Metadata } from "next";

import AnimeListingPage from "@/components/anime/anime_listing_page";

export const metadata: Metadata = {
    title: "Ongoing - HitoriBocchi",
};

export default function OngoingPage() {
    return <AnimeListingPage title="Ongoing Animes" view="ongoing" />;
}
