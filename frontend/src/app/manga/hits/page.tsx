import type { Metadata } from "next";

import MangaListingPage from "@/components/manga/manga_listing_page";

export const metadata: Metadata = {
  title: "Manga Hits - HitoriBocchi",
};

export default function MangaHitsPage() {
  return <MangaListingPage title="Top Manga Hits" view="hits" />;
}
