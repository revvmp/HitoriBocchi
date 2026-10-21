"use client";

import { useState } from "react";

import {
  EPISODE_STREAM_QUALITIES,
  type EpisodeStreamQuality,
} from "@/lib/api/episode";

type PlayerSettingsMenuProps = {
  onQualitySelect: (quality: EpisodeStreamQuality) => void;
  onSubtitleOpacityChange: (opacity: number) => void;
  quality: EpisodeStreamQuality;
  subtitleOpacity: number;
};

// Rendered inside the Video.js control bar through a portal.
export default function PlayerSettingsMenu({
  onQualitySelect,
  onSubtitleOpacityChange,
  quality,
  subtitleOpacity,
}: PlayerSettingsMenuProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div
      className="relative size-full"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setIsOpen(false);
        }
      }}
    >
      <button
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-label={`Player settings, quality: ${quality}`}
        className="vjs-button size-full"
        onClick={() => setIsOpen((currentIsOpen) => !currentIsOpen)}
        title="Player settings"
        type="button"
      >
        <span
          aria-hidden="true"
          className="vjs-icon-placeholder vjs-icon-cog"
        />
        <span className="vjs-control-text">Player settings</span>
      </button>

      {isOpen && (
        <div
          aria-label="Player settings"
          className="absolute right-0 bottom-full z-50 mb-2 max-h-[60vh] w-60 max-w-[75vw] overflow-y-auto rounded-md border border-home-surface bg-home-background py-1 shadow-2xl"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setIsOpen(false);
              event.currentTarget.parentElement?.querySelector("button")?.focus();
            }
          }}
          role="dialog"
        >
          <label className="block border-b border-home-surface px-3 py-2 text-xs text-home-text">
            <span className="flex items-center justify-between gap-3">
              <span>Subtitle background opacity</span>
              <span>{subtitleOpacity}%</span>
            </span>
            <input
              aria-label="Subtitle background opacity"
              aria-valuetext={`${subtitleOpacity}%`}
              className="mt-1 block h-8 w-full cursor-pointer accent-home-accent"
              max={100}
              min={0}
              onChange={(event) => onSubtitleOpacityChange(Number(event.target.value))}
              step={1}
              type="range"
              value={subtitleOpacity}
            />
          </label>
          <div aria-label="Quality" role="menu">
            {EPISODE_STREAM_QUALITIES.map((streamQuality) => (
              <button
                aria-checked={streamQuality === quality}
                className={
                  "flex w-full items-center px-3 py-2 text-left text-xs text-home-text hover:bg-home-surface "
                  + (streamQuality === quality
                    ? "font-bold"
                    : "font-normal")
                }
                key={streamQuality}
                onClick={() => {
                  setIsOpen(false);
                  onQualitySelect(streamQuality);
                }}
                role="menuitemradio"
                type="button"
              >
                {streamQuality}
                {streamQuality === quality && (
                  <span
                    aria-hidden="true"
                    className="ml-2 inline-block size-1.5 rounded-full bg-home-text shadow-[0_0_6px_var(--home-text)]"
                  />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
