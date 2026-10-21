import MangaGrid from "@/components/manga/manga_grid";
import type { MangaView } from "@/lib/api/manga";

type MangaListingPageProps = {
  description?: string;
  searchQuery?: string;
  title: string;
  view: MangaView;
};

export default function MangaListingPage({
  description,
  searchQuery,
  title,
  view,
}: MangaListingPageProps) {
  return (
    <main className="min-h-svh bg-home-background px-4 py-5 text-home-text sm:px-7 sm:py-7 lg:px-10 xl:px-12 2xl:px-18">
      <div className="mx-auto w-full max-w-[120rem]">
        <header className="mb-5 border-b border-home-surface pb-3">
          <h1 className="text-[1.375rem] font-semibold tracking-tight sm:text-[1.625rem]">
            {title}
          </h1>
          {description && (
            <p className="mt-1.5 text-sm text-home-muted">{description}</p>
          )}
        </header>

        <MangaGrid
          key={view + "-" + (searchQuery ?? "")}
          searchQuery={searchQuery}
          view={view}
        />
      </div>
    </main>
  );
}
