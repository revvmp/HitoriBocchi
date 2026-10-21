import type { MangaPage } from "@/lib/api/manga";

type PageProgressIndicatorProps = {
  activePageIndex: number;
  pages: MangaPage[];
};

export default function PageProgressIndicator({
  activePageIndex,
  pages,
}: PageProgressIndicatorProps) {
  if (pages.length === 0) {
    return null;
  }

  const currentPageIndex = Math.min(
    Math.max(activePageIndex, 0),
    pages.length - 1,
  );

  return (
    <div
      aria-label={`Page ${currentPageIndex + 1} of ${pages.length}`}
      aria-valuemax={pages.length}
      aria-valuemin={1}
      aria-valuenow={currentPageIndex + 1}
      className="pointer-events-none fixed inset-y-0 left-0 z-[60] flex w-0.5 flex-col gap-px bg-home-background/50 py-0.5 sm:w-1"
      role="progressbar"
    >
      {pages.map((page, index) => (
        <span
          aria-hidden="true"
          className={`min-h-px flex-1 transition-colors duration-150 ${
            index === currentPageIndex
              ? "bg-home-accent"
              : index < currentPageIndex
                ? "bg-home-accent/60"
                : "bg-home-muted/30"
          }`}
          key={`${page.page}-${index}`}
        />
      ))}
    </div>
  );
}
