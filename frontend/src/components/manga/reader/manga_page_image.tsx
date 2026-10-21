import Image from "next/image";

import type { MangaPage } from "@/lib/api/manga";

type MangaPageImageProps = {
  chapterNumber: string;
  className: string;
  eager: boolean;
  failed: boolean;
  onError: () => void;
  page: MangaPage;
  sizes: string;
  title: string;
};

export default function MangaPageImage({
  chapterNumber,
  className,
  eager,
  failed,
  onError,
  page,
  sizes,
  title,
}: MangaPageImageProps) {
  const width = (
    typeof page.width === "number" && page.width > 0
      ? page.width
      : 1200
  );
  const height = (
    typeof page.height === "number" && page.height > 0
      ? page.height
      : 1800
  );

  if (failed) {
    return (
      <div
        className="flex min-h-48 w-full items-center justify-center border border-home-surface bg-home-surface/30 px-4 text-center text-sm text-home-muted"
        role="status"
      >
        Page {page.page} could not be loaded. Refresh to try again.
      </div>
    );
  }

  return (
    <Image
      alt={`${title}, chapter ${chapterNumber}, page ${page.page}`}
      className={className}
      fetchPriority={eager ? "high" : "auto"}
      height={height}
      loading={eager ? "eager" : "lazy"}
      onError={onError}
      sizes={sizes}
      src={page.image_url}
      unoptimized
      width={width}
    />
  );
}
