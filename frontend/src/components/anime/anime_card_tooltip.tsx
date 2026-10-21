import CardTooltip from "@/components/common/card_tooltip";
import type { AnimeSummary } from "@/lib/api/anime";

type AnimeCardTooltipProps = {
  anime: AnimeSummary;
};

export default function AnimeCardTooltip({
  anime,
}: AnimeCardTooltipProps) {
  const status =
    anime.status === "Currently Airing" ? "Airing" : anime.status;
  const totalEpisodes = anime.total_episodes || "?";

  return (
    <CardTooltip
      className="anime-card-tooltip"
      genres={anime.genres}
      id={`anime-details-${anime.id}`}
      stats={[
        {
          label: "Score",
          value: anime.rating > 0 ? `${anime.rating}/10` : "Not rated",
        },
        {
          label: "Episodes",
          value: `${anime.current_episodes} / ${totalEpisodes}`,
        },
        { label: "Status", value: status || "Unknown" },
        {
          label: "Popularity",
          value: anime.popularity ? `#${anime.popularity}` : "Unranked",
        },
      ]}
      synopsis={anime.synopsis}
      title={anime.title}
      titleEnglish={anime.title_english}
    />
  );
}
