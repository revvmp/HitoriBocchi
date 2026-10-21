import type { Metadata } from "next";

import ContinueWatchingGrid from "@/components/anime/continue_watching_grid";

export const metadata: Metadata = {
    title: "Continue Watching - HitoriBocchi",
};

export default function ContinueWatching() {
    return (
        <main className="min-h-svh bg-home-background px-4 py-5 text-home-text sm:px-7 sm:py-7 lg:px-10 xl:px-12 2xl:px-18">
            <div className="mx-auto w-full max-w-[120rem]">
                <ContinueWatchingGrid />
            </div>
        </main>
    );
}
