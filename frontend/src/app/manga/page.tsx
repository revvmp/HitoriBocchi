import type { Metadata } from "next";

import MangaListingPage from "@/components/manga/manga_listing_page";

export const metadata: Metadata = {
  title: "Manga - HitoriBocchi",
  description: "Recently updated manga and manhwa on HitoriBocchi.",
};

export default function MangaHomePage() {
  return (
    <MangaListingPage
      description="Continue from the newest chapters added to the library."
      title="Latest Chapters"
      view="latest"
    />
  );
}
