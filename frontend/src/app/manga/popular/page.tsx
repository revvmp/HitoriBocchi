import type { Metadata } from "next";

import MangaListingPage from "@/components/manga/manga_listing_page";

export const metadata: Metadata = {
  title: "Popular Manga - HitoriBocchi",
};

export default function PopularMangaPage() {
  return <MangaListingPage title="Popular Manga" view="popular" />;
}
