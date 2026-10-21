"use client";

import { useEffect, useEffectEvent, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type Player from "video.js/dist/types/player";

import * as playerPreferences from "@/components/player/player_preferences";
import { attachPlayerSeekGestures, type SeekOffset } from "@/components/player/player_seek_gestures";
import PlayerSettingsMenu from "@/components/player/player_settings_menu";
import {
  getEpisodeSkipTimes,
  type EpisodeSkipTime,
  type EpisodeStreamQuality,
} from "@/lib/api/episode";
import * as mobileHls from "@/lib/player/mobile_hls";
import { bridgeNativeFullscreenSubtitles } from "@/lib/player/video_subtitles";

import "video.js/dist/video-js.css";

type VideoPlayerProps = {
  episodeNumber: number;
  initialTimeSeconds?: number;
  onComplete?: (
    currentTimeSeconds: number,
    durationSeconds: number,
  ) => void;
  onQualityChange: (
    quality: EpisodeStreamQuality,
    currentTimeSeconds: number,
  ) => void;
  onTimeChange?: (currentTimeSeconds: number) => void;
  onProgress?: (
    currentTimeSeconds: number,
    durationSeconds: number,
    keepalive: boolean,
  ) => void;
  quality: EpisodeStreamQuality;
  slug: string;
  src: string;
  subtitleSrc?: string;
};

function getSourceType(src: string) {
  const pathname = new URL(src, window.location.origin).pathname.toLowerCase();

  if (pathname.endsWith(".m3u8")) {
    return "application/x-mpegURL";
  }

  if (pathname.endsWith(".mpd")) {
    return "application/dash+xml";
  }

  if (pathname.endsWith(".webm")) {
    return "video/webm";
  }

  if (pathname.endsWith(".mp4")) {
    return "video/mp4";
  }

  return undefined;
}

export default function VideoPlayer({
  episodeNumber,
  initialTimeSeconds = 0,
  onComplete,
  onQualityChange,
  onTimeChange,
  onProgress,
  quality,
  slug,
  src,
  subtitleSrc,
}: VideoPlayerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<Player | null>(null);
  const seekFeedbackTimeoutRef = useRef<number | null>(null);
  const skipTimesRef = useRef<EpisodeSkipTime[]>([]);
  const subtitleOpacityRef = useRef(playerPreferences.DEFAULT_SUBTITLE_OPACITY);
  const [subtitleOpacity, setSubtitleOpacity] = useState(
    playerPreferences.DEFAULT_SUBTITLE_OPACITY,
  );
  const [playerElement, setPlayerElement] = useState<HTMLElement | null>(null);
  const [qualityControlElement, setQualityControlElement] =
    useState<HTMLElement | null>(null);
  const [seekFeedback, setSeekFeedback] = useState<SeekOffset | null>(null);
  const [activeSkipTime, setActiveSkipTime] =
    useState<EpisodeSkipTime | null>(null);

  const notifyProgress = useEffectEvent((currentTime: number, duration: number, keepalive: boolean) => {
    onProgress?.(currentTime, duration, keepalive);
  });
  const notifyCompletion = useEffectEvent((currentTime: number, duration: number) => {
    onComplete?.(currentTime, duration);
  });
  const notifyTimeChange = useEffectEvent((currentTime: number) => {
    onTimeChange?.(currentTime);
  });

  useEffect(() => {
    return () => {
      if (seekFeedbackTimeoutRef.current !== null) {
        window.clearTimeout(seekFeedbackTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    let isActive = true;
    skipTimesRef.current = [];

    if (!containerRef.current) {
      return;
    }

    const container = containerRef.current;

    async function initializePlayer() {
      const { default: videojs } = await import("video.js");
      let sourceType = getSourceType(src);
      let useMobileHls = false;

      if (mobileHls.isMobileHlsSource(src, window.location.origin, videojs.browser.IS_IOS || videojs.browser.IS_ANDROID)) {
        try {
          const { default: Hls } = await import("hls.js");

          if (Hls.isSupported() && mobileHls.registerMobileHls(videojs.getTech("Html5"), Hls)) {
            sourceType = mobileHls.MOBILE_HLS_TYPE;
            useMobileHls = true;
          }
        } catch {
          // Retain the existing playback path if the optional engine cannot load.
        }
      }

      if (!isActive) {
        return;
      }

      const videoElement = document.createElement("video-js");
      videoElement.classList.add(
        "hitoribocchi-player",
        "vjs-big-play-centered",
      );

      container.appendChild(videoElement);

      const player = videojs(videoElement, {
        controlBar: {
          skipButtons: {
            backward: 10,
            forward: 10,
          },
        },
        controls: true,
        fill: true,
        // Keep external subtitles in the renderer controlled by our opacity setting.
        html5: {
          nativeAudioTracks: useMobileHls ? false : undefined,
          nativeVideoTracks: useMobileHls ? false : undefined,
          nativeTextTracks: subtitleSrc ? false : undefined,
        },
        playsinline: true,
        preload: "metadata",
        responsive: true,
        sources: [
          {
            src,
            ...(sourceType ? { type: sourceType } : {}),
            ...(useMobileHls ? { externalSubtitles: Boolean(subtitleSrc) } : {}),
          },
        ],
        tracks: subtitleSrc
          ? [
              {
                default: true,
                kind: "subtitles",
                label: "English",
                language: "en",
                src: subtitleSrc,
              },
            ]
          : [],
      });

      player.ready(() => {
        if (!isActive || player.isDisposed() || !subtitleSrc) {
          return;
        }

        const video = player.el()?.querySelector("video");

        if (video) {
          const cleanupSubtitles = bridgeNativeFullscreenSubtitles(video, subtitleSrc, () => {
            const tracks = player.textTracks() as unknown as ArrayLike<TextTrack>;

            for (let index = 0; index < tracks.length; index += 1) {
              const track = tracks[index];

              if (track.kind === "subtitles" && track.language === "en") {
                return track;
              }
            }
          });
          player.one("dispose", cleanupSubtitles);
        }
      });

      playerRef.current = player;
      playerPreferences.restorePlayerVolume(player);
      player.on("volumechange", handleVolumeChange);

      const element = player.el();

      if (element instanceof HTMLElement) {
        subtitleOpacityRef.current = playerPreferences.loadSubtitleOpacity(
          subtitleOpacityRef.current,
        );
        playerPreferences.applySubtitleOpacity(element, subtitleOpacityRef.current);
        setSubtitleOpacity(subtitleOpacityRef.current);
        setPlayerElement(element);
      }

      const controlBarElement = player.getChild("ControlBar")?.el();

      if (controlBarElement instanceof HTMLElement) {
        const qualityControlTarget = document.createElement("div");
        const pictureInPictureControl = controlBarElement.querySelector(
          ".vjs-picture-in-picture-control",
        );
        const fullscreenControl = controlBarElement.querySelector(
          ".vjs-fullscreen-control",
        );

        qualityControlTarget.classList.add(
          "episode-quality-control",
          "vjs-control",
        );
        controlBarElement.insertBefore(
          qualityControlTarget,
          pictureInPictureControl || fullscreenControl,
        );
        setQualityControlElement(qualityControlTarget);
      }

      let lastReportedTime = initialTimeSeconds;
      let hasReportedCompletion = false;
      let requestedSkipTimes = false;

      function handleVolumeChange() {
        playerPreferences.savePlayerVolume(player);
      }

      function getPlaybackTime() {
        const currentTime = player.currentTime();
        const duration = player.duration();

        if (
          typeof currentTime !== "number"
          || typeof duration !== "number"
          || !Number.isFinite(currentTime)
          || !Number.isFinite(duration)
          || currentTime <= 0
          || duration <= 0
        ) {
          return null;
        }

        return {
          currentTime,
          duration,
        };
      }

      function reportProgress(keepalive = false) {
        const playbackTime = getPlaybackTime();

        if (!playbackTime) {
          return;
        }

        lastReportedTime = playbackTime.currentTime;
        notifyProgress(
          playbackTime.currentTime,
          playbackTime.duration,
          keepalive,
        );
      }

      function reportCompletion() {
        if (hasReportedCompletion) {
          return;
        }

        const playbackTime = getPlaybackTime();

        if (
          !playbackTime
          || playbackTime.currentTime < playbackTime.duration * 0.9
        ) {
          return;
        }

        hasReportedCompletion = true;
        notifyCompletion(playbackTime.currentTime, playbackTime.duration);
      }

      function showSeekFeedback(seconds: SeekOffset) {
        if (seekFeedbackTimeoutRef.current !== null) {
          window.clearTimeout(seekFeedbackTimeoutRef.current);
        }

        setSeekFeedback(seconds);
        seekFeedbackTimeoutRef.current = window.setTimeout(() => {
          setSeekFeedback(null);
          seekFeedbackTimeoutRef.current = null;
        }, 650);
      }

      function updateActiveSkipTime(currentTime: number) {
        const nextSkipTime = skipTimesRef.current.find(
          (skipTime) =>
            currentTime >= skipTime.start_time
            && currentTime < skipTime.end_time,
        ) ?? null;

        setActiveSkipTime((currentSkipTime) => {
          if (
            currentSkipTime?.skip_type === nextSkipTime?.skip_type
            && currentSkipTime?.start_time === nextSkipTime?.start_time
            && currentSkipTime?.end_time === nextSkipTime?.end_time
          ) {
            return currentSkipTime;
          }

          return nextSkipTime;
        });
      }

      function loadSkipTimes(duration: number) {
        if (requestedSkipTimes) {
          return;
        }

        requestedSkipTimes = true;

        void getEpisodeSkipTimes(slug, episodeNumber, duration)
          .then((response) => {
            if (!isActive || player.isDisposed()) {
              return;
            }

            skipTimesRef.current = response.skip_times;

            const currentTime = player.currentTime();

            if (typeof currentTime === "number") {
              updateActiveSkipTime(currentTime);
            }
          })
          .catch(() => {
            skipTimesRef.current = [];
          });
      }

      player.one("loadedmetadata", () => {
        const duration = player.duration();

        if (typeof duration !== "number" || !Number.isFinite(duration)) {
          return;
        }

        loadSkipTimes(duration);

        if (
          initialTimeSeconds > 0
          && Number.isFinite(initialTimeSeconds)
        ) {
          const resumeTime = Math.min(initialTimeSeconds, duration - 1);
          player.currentTime(resumeTime);
          lastReportedTime = resumeTime;
        }
      });

      player.on("timeupdate", () => {
        const currentTime = player.currentTime();

        if (typeof currentTime === "number" && Number.isFinite(currentTime)) {
          notifyTimeChange(currentTime);
          updateActiveSkipTime(currentTime);
        }

        reportCompletion();

        if (
          typeof currentTime === "number"
          && Math.abs(currentTime - lastReportedTime) >= 15
        ) {
          reportProgress();
        }
      });

      player.on("pause", () => {
        reportProgress();
      });

      player.on("ended", () => {
        reportCompletion();
        reportProgress();
      });

      function handlePageHide() {
        reportProgress(true);
      }

      function handleVisibilityChange() {
        if (document.visibilityState === "hidden") {
          reportProgress(true);
        }
      }

      window.addEventListener("pagehide", handlePageHide);
      document.addEventListener("visibilitychange", handleVisibilityChange);

      const detachSeekGestures = attachPlayerSeekGestures(
        player,
        element,
        showSeekFeedback,
      );

      player.one("dispose", () => {
        player.off("volumechange", handleVolumeChange);
        window.removeEventListener("pagehide", handlePageHide);
        document.removeEventListener(
          "visibilitychange",
          handleVisibilityChange,
        );
        detachSeekGestures();
      });
    }

    void initializePlayer();

    return () => {
      isActive = false;

      const player = playerRef.current;

      if (player && !player.isDisposed()) {
        player.dispose();
      }

      playerRef.current = null;
    };
  }, [
    episodeNumber,
    initialTimeSeconds,
    slug,
    src,
    subtitleSrc,
  ]);

  function handleSkip() {
    const player = playerRef.current;

    if (!activeSkipTime || !player || player.isDisposed()) {
      return;
    }

    player.currentTime(activeSkipTime.end_time);
    setActiveSkipTime(null);
  }

  function handleSubtitleOpacityChange(opacity: number) {
    subtitleOpacityRef.current = opacity;
    setSubtitleOpacity(opacity);

    const element = playerRef.current?.el();

    if (element instanceof HTMLElement) {
      playerPreferences.applySubtitleOpacity(element, opacity);
    }

    playerPreferences.saveSubtitleOpacity(opacity);
  }

  function handleQualitySelection(nextQuality: EpisodeStreamQuality) {
    if (nextQuality === quality) {
      return;
    }

    const player = playerRef.current;

    if (!player || player.isDisposed()) {
      return;
    }

    const currentTime = player.currentTime();
    const currentTimeSeconds =
      typeof currentTime === "number" && Number.isFinite(currentTime)
        ? currentTime
        : 0;

    onQualityChange(nextQuality, currentTimeSeconds);
  }

  return (
    <div className="relative size-full" data-vjs-player>
      <div className="size-full" ref={containerRef} />

      {qualityControlElement && createPortal(
        <PlayerSettingsMenu
          onQualitySelect={handleQualitySelection}
          onSubtitleOpacityChange={handleSubtitleOpacityChange}
          quality={quality}
          subtitleOpacity={subtitleOpacity}
        />,
        qualityControlElement,
      )}

      {activeSkipTime && playerElement && createPortal(
        <button
          className="episode-skip-button absolute right-3 bottom-14 z-20 rounded-md px-5 py-3 text-sm font-bold tracking-wide shadow-2xl transition focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none sm:right-4 sm:bottom-16 sm:px-6 sm:text-base"
          onClick={handleSkip}
          type="button"
        >
          Skip {activeSkipTime.skip_type === "opening" ? "Opening" : "Ending"}
          <span className="ml-2" aria-hidden="true">&rarr;</span>
        </button>,
        playerElement,
      )}

      {seekFeedback !== null && playerElement && createPortal(
        <div
          className={
            "pointer-events-none absolute inset-y-0 z-20 flex w-1/2 items-center justify-center "
            + (seekFeedback < 0 ? "left-0" : "right-0")
          }
        >
          <span
            className="rounded-full bg-home-background/80 px-4 py-3 text-sm font-bold text-home-text shadow-2xl"
            role="status"
          >
            {seekFeedback > 0 ? "+10 seconds" : "-10 seconds"}
          </span>
        </div>,
        playerElement,
      )}
    </div>
  );
}
