// Grid layout shared by the anime and manga catalogs; callers prefix the
// catalog-specific class that globals.css uses to position card tooltips.
export const CATALOG_GRID_CLASS_NAME =
  "grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-3 sm:gap-x-4 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-8 xl:gap-x-5 2xl:grid-cols-9";

type CatalogGridSkeletonProps = {
  className: string;
  label: string;
};

export default function CatalogGridSkeleton({
  className,
  label,
}: CatalogGridSkeletonProps) {
  return (
    <div className={className} aria-label={label}>
      {Array.from({ length: 12 }, (_, index) => (
        <div className="animate-pulse" key={index}>
          <div className="aspect-[2/3] rounded-md bg-home-surface" />
          <div className="mt-2 h-4 w-4/5 rounded bg-home-surface" />
        </div>
      ))}
    </div>
  );
}
