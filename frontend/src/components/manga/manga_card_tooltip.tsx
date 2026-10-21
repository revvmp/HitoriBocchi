import CardTooltip from "@/components/common/card_tooltip";
import type { MangaSummary } from "@/lib/api/manga";

type MangaCardTooltipProps = {
  manga: MangaSummary;
};

export default function MangaCardTooltip({
  manga,
}: MangaCardTooltipProps) {
  const totalChapters = manga.total_chapters || "?";

  return (
    <CardTooltip
      className="manga-card-tooltip"
      genres={manga.genres}
      id={`manga-details-${manga.id}`}
      stats={[
        {
          label: "Score",
          value: manga.rating > 0 ? `${manga.rating}/10` : "Not rated",
        },
        {
          label: "Chapters",
          value: `${manga.current_chapters} / ${totalChapters}`,
        },
        { label: "Status", value: manga.status || "Unknown" },
        { label: "Type", value: manga.media_type || "Manga" },
      ]}
      synopsis={manga.synopsis}
      title={manga.title}
      titleEnglish={manga.title_english}
    />
  );
}
