import * as readerSettings from "@/components/manga/reader/reader_settings";

type ZoomControlsProps = {
  onZoomChange: (nextZoom: number) => void;
  zoomLevel: number;
};

export default function ZoomControls({
  onZoomChange,
  zoomLevel,
}: ZoomControlsProps) {
  return (
    <div
      aria-label="Page zoom"
      className="inline-grid h-11 grid-cols-[2.75rem_minmax(4.25rem,auto)_2.75rem] overflow-hidden rounded-md border border-home-surface bg-home-surface/30"
      role="group"
    >
      <button
        aria-label="Zoom out"
        className="flex items-center justify-center border-r border-home-surface text-lg font-semibold text-home-muted transition hover:bg-home-surface hover:text-home-text focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-home-accent disabled:cursor-not-allowed disabled:opacity-40"
        disabled={zoomLevel <= readerSettings.MIN_READER_ZOOM}
        onClick={() => onZoomChange(zoomLevel - readerSettings.READER_ZOOM_STEP)}
        title="Zoom out"
        type="button"
      >
        <span aria-hidden="true">−</span>
      </button>
      <button
        aria-label={`Reset zoom from ${zoomLevel.toFixed(1)}x to 1.0x`}
        className="px-2 text-xs font-semibold tabular-nums text-home-text transition hover:bg-home-surface focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-home-accent"
        onClick={() => onZoomChange(readerSettings.DEFAULT_READER_ZOOM)}
        title="Reset zoom"
        type="button"
      >
        {zoomLevel.toFixed(1)}x
      </button>
      <button
        aria-label="Zoom in"
        className="flex items-center justify-center border-l border-home-surface text-lg font-semibold text-home-muted transition hover:bg-home-surface hover:text-home-text focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-home-accent disabled:cursor-not-allowed disabled:opacity-40"
        disabled={zoomLevel >= readerSettings.MAX_READER_ZOOM}
        onClick={() => onZoomChange(zoomLevel + readerSettings.READER_ZOOM_STEP)}
        title="Zoom in"
        type="button"
      >
        <span aria-hidden="true">+</span>
      </button>
    </div>
  );
}
