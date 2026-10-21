import type { Metadata } from "next";

import AnimeDetails from "@/components/anime/anime_details";

export const metadata: Metadata = {
    title: "Anime - HitoriBocchi",
};

type AnimePageProps = {
    params: Promise<{ slug: string }>;
};

export default async function AnimePage({ params }: AnimePageProps) {
    const { slug } = await params;

    return <AnimeDetails key={slug} slug={slug} />;
}
