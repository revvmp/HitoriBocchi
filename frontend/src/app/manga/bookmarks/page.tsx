import type { Metadata } from "next";

import MangaListingPage from "@/components/manga/manga_listing_page";

export const metadata: Metadata = {
  title: "Manga Bookmarks - HitoriBocchi",
};

export default function MangaBookmarksPage() {
  return (
    <MangaListingPage
      description="Your saved manga and manhwa in one place."
      title="Bookmarks"
      view="bookmarks"
    />
  );
}
