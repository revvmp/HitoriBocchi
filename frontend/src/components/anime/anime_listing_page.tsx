import AnimeGrid from "@/components/anime/anime_grid";
import type { AnimeView } from "@/lib/api/anime";

type AnimeListingPageProps = {
  searchQuery?: string;
  title: string;
  view: AnimeView;
};

export default function AnimeListingPage({
  searchQuery,
  title,
  view,
}: AnimeListingPageProps) {
  return (
    <main className="min-h-svh bg-home-background px-4 py-5 text-home-text sm:px-7 sm:py-7 lg:px-10 xl:px-12 2xl:px-18">
      <div className="mx-auto w-full max-w-[120rem]">
        <header className="mb-5 border-b border-home-surface pb-3">
          <h1 className="text-[1.375rem] font-semibold tracking-tight sm:text-[1.625rem]">
            {title}
          </h1>
        </header>

        <AnimeGrid
          key={view + "-" + (searchQuery ?? "")}
          searchQuery={searchQuery}
          view={view}
        />
      </div>
    </main>
  );
}
