import {
  EPISODE_STREAM_CATEGORIES,
  type EpisodeStreamCategory,
  type EpisodeStreamProvider,
} from "@/lib/api/episode";

type EpisodeStreamServer = {
  label: string;
  value: EpisodeStreamProvider;
};

type EpisodeStreamSelectorsProps = {
  categories: EpisodeStreamCategory[];
  isLoadingStream: boolean;
  onCategoryChange: (category: EpisodeStreamCategory) => void;
  onServerChange: (provider: EpisodeStreamProvider) => void;
  selectedCategory: EpisodeStreamCategory;
  selectedProvider: EpisodeStreamProvider;
  servers: readonly EpisodeStreamServer[];
};

const selectorLabelClassName =
  "inline-flex items-center gap-2 rounded-md border border-home-surface bg-home-surface/30 px-2.5 py-1.5 transition hover:bg-home-surface focus-within:border-home-accent";
const selectClassName =
  "cursor-pointer bg-home-background text-xs font-semibold text-home-text outline-none disabled:cursor-wait disabled:opacity-60";

export default function EpisodeStreamSelectors({
  categories,
  isLoadingStream,
  onCategoryChange,
  onServerChange,
  selectedCategory,
  selectedProvider,
  servers,
}: EpisodeStreamSelectorsProps) {
  return (
    <div className="mt-2 flex justify-end gap-2">
      <label className={selectorLabelClassName} htmlFor="episode-category">
        <span className="text-xs font-normal text-home-muted">Version</span>
        <select
          aria-label="Episode version"
          className={selectClassName}
          disabled={isLoadingStream}
          id="episode-category"
          onChange={(event) => {
            onCategoryChange(event.target.value as EpisodeStreamCategory);
          }}
          value={selectedCategory}
        >
          {EPISODE_STREAM_CATEGORIES.filter((category) =>
            categories.includes(category.value)
          ).map((category) => (
            <option key={category.value} value={category.value}>
              {category.label}
            </option>
          ))}
        </select>
      </label>
      <label className={selectorLabelClassName} htmlFor="episode-server">
        <span className="text-xs font-normal text-home-muted">Server</span>
        <select
          aria-label="Streaming server"
          className={selectClassName}
          disabled={servers.length < 2}
          id="episode-server"
          onChange={(event) => {
            onServerChange(event.target.value as EpisodeStreamProvider);
          }}
          value={selectedProvider}
        >
          {servers.map((server) => (
            <option key={server.value} value={server.value}>
              {server.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
