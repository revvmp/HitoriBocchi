type CardTooltipStat = {
  label: string;
  value: string | number;
};

type CardTooltipProps = {
  className: string;
  genres: string[];
  id: string;
  stats: CardTooltipStat[];
  synopsis: string;
  title: string;
  titleEnglish: string;
};

// Hover/focus details shown beside catalog cards. The className carries the
// catalog-specific class that globals.css uses to position tooltips in grids.
export default function CardTooltip({
  className,
  genres,
  id,
  stats,
  synopsis,
  title,
  titleEnglish,
}: CardTooltipProps) {
  return (
    <div
      id={id}
      role="tooltip"
      className={`${className} invisible absolute top-0 left-[calc(100%+0.75rem)] z-50 w-36 rounded-md border border-home-accent/40 bg-home-background/95 p-3 text-home-text opacity-0 shadow-xl backdrop-blur-sm transition duration-200 group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100 sm:w-52 md:w-64 lg:w-72 xl:w-80`}
    >
      <h3 className="line-clamp-2 text-sm font-semibold leading-5">
        {titleEnglish || title}
      </h3>

      {titleEnglish && titleEnglish !== title && (
        <p className="mt-1 line-clamp-2 text-xs text-home-muted">
          Original: {title}
        </p>
      )}

      <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
        {stats.map((stat) => (
          <div key={stat.label}>
            <dt className="text-home-muted">{stat.label}</dt>
            <dd className="font-semibold">{stat.value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-3">
        <p className="text-xs font-semibold">Synopsis</p>
        <p className="mt-1 line-clamp-5 text-xs leading-4 text-home-muted">
          {synopsis || "No synopsis available."}
        </p>
      </div>

      <div className="mt-3">
        <p className="text-xs font-semibold">Genres</p>
        <div className="mt-1.5 flex flex-wrap gap-1">
          {genres.length > 0 ? (
            genres.map((genre) => (
              <span
                className="rounded-sm bg-home-surface px-1.5 py-0.5 text-[10px] text-home-text"
                key={genre}
              >
                {genre}
              </span>
            ))
          ) : (
            <span className="text-xs text-home-muted">Unknown</span>
          )}
        </div>
      </div>
    </div>
  );
}
