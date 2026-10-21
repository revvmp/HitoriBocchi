import type { Metadata } from "next";

import MangaReader from "@/components/manga/reader/manga_reader";

export const metadata: Metadata = {
  title: "Read Manga - HitoriBocchi",
};

type MangaChapterPageProps = {
  params: Promise<{ chapterNumber: string; slug: string }>;
};

export default async function MangaChapterPage({
  params,
}: MangaChapterPageProps) {
  const { chapterNumber, slug } = await params;

  return (
    <MangaReader
      chapterNumber={chapterNumber}
      key={`${slug}-${chapterNumber}`}
      slug={slug}
    />
  );
}
