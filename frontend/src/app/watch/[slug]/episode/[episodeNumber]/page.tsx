import type { Metadata } from "next";

import EpisodeWatch from "@/components/episode/episode_watch";

export const metadata: Metadata = {
    title: "Watch Episode - HitoriBocchi",
};

type EpisodePageProps = {
    params: Promise<{
        slug: string;
        episodeNumber: string;
    }>;
};

export default async function EpisodePage({ params }: EpisodePageProps) {
    const { slug, episodeNumber } = await params;
    const parsedEpisodeNumber = Number(episodeNumber);

    return (
        <EpisodeWatch
            key={`${slug}-${episodeNumber}`}
            episodeNumber={parsedEpisodeNumber}
            slug={slug}
        />
    );
}
