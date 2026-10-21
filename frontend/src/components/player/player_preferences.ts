import type Player from "video.js/dist/types/player";

const VIDEO_PLAYER_MUTED_KEY = "hitoribocchi-video-player-muted";
const VIDEO_PLAYER_VOLUME_KEY = "hitoribocchi-video-player-volume";
const VIDEO_PLAYER_SUBTITLE_OPACITY_KEY = "hitoribocchi-video-player-subtitle-opacity";

export const DEFAULT_SUBTITLE_OPACITY = 65;

export function restorePlayerVolume(player: Player) {
  try {
    const savedVolume = Number.parseFloat(
      window.localStorage.getItem(VIDEO_PLAYER_VOLUME_KEY) || "",
    );
    const savedMuted = window.localStorage.getItem(VIDEO_PLAYER_MUTED_KEY);

    if (Number.isFinite(savedVolume)) {
      player.volume(Math.min(1, Math.max(0, savedVolume)));
    }

    if (savedMuted === "true" || savedMuted === "false") {
      player.muted(savedMuted === "true");
    }
  } catch {
    // The default player volume remains when browser storage is unavailable.
  }
}

export function savePlayerVolume(player: Player) {
  const volume = player.volume();
  const muted = player.muted();

  if (
    typeof volume !== "number"
    || !Number.isFinite(volume)
    || typeof muted !== "boolean"
  ) {
    return;
  }

  try {
    window.localStorage.setItem(VIDEO_PLAYER_VOLUME_KEY, String(volume));
    window.localStorage.setItem(VIDEO_PLAYER_MUTED_KEY, String(muted));
  } catch {
    // Volume changes still work for the current player without storage.
  }
}

export function loadSubtitleOpacity(currentOpacity: number) {
  try {
    const savedOpacity = Number.parseFloat(
      window.localStorage.getItem(VIDEO_PLAYER_SUBTITLE_OPACITY_KEY) || "",
    );

    if (Number.isFinite(savedOpacity)) {
      return Math.round(Math.min(100, Math.max(0, savedOpacity)));
    }
  } catch {
    // Keep the current preference when browser storage is unavailable.
  }

  return currentOpacity;
}

export function saveSubtitleOpacity(opacity: number) {
  try {
    window.localStorage.setItem(VIDEO_PLAYER_SUBTITLE_OPACITY_KEY, String(opacity));
  } catch {
    // Subtitle changes still work for the current player without storage.
  }
}

// The inline Video.js cue background reads this CSS variable.
export function applySubtitleOpacity(element: HTMLElement, opacity: number) {
  element.style.setProperty("--player-subtitle-opacity", `${opacity}%`);
}
