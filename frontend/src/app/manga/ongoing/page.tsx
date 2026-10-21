import type { Metadata } from "next";

import MangaListingPage from "@/components/manga/manga_listing_page";

export const metadata: Metadata = {
  title: "Ongoing Manga - HitoriBocchi",
};

export default function OngoingMangaPage() {
  return <MangaListingPage title="Ongoing Manga" view="ongoing" />;
}
