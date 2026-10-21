import type { Metadata } from "next";

import MangaDetails from "@/components/manga/manga_details";

export const metadata: Metadata = {
  title: "Manga - HitoriBocchi",
};

type MangaPageProps = {
  params: Promise<{ slug: string }>;
};

export default async function MangaPage({ params }: MangaPageProps) {
  const { slug } = await params;

  return <MangaDetails key={slug} slug={slug} />;
}
