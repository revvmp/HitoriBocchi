import type Player from "video.js/dist/types/player";

export type SeekOffset = -10 | 10;

type TouchStart = {
  clientX: number;
  clientY: number;
  startedAt: number;
};

export function seekPlayerBy(player: Player, seconds: number) {
  const currentTime = player.currentTime();
  const duration = player.duration();

  if (
    typeof currentTime !== "number"
    || typeof duration !== "number"
    || !Number.isFinite(currentTime)
    || !Number.isFinite(duration)
  ) {
    return false;
  }

  player.currentTime(
    Math.min(Math.max(currentTime + seconds, 0), duration),
  );
  return true;
}

function isPlayerControl(target: EventTarget | null) {
  return (
    target instanceof Element
    && target.closest(
      ".vjs-control-bar, .vjs-modal-dialog, .episode-skip-button",
    ) !== null
  );
}

// Adds double-tap seeking on either half of the player and arrow-key seeking.
// Returns a cleanup function that removes every listener it added.
export function attachPlayerSeekGestures(player: Player, element: Element, onDoubleTapSeek: (seconds: SeekOffset) => void) {
  let touchStart: TouchStart | null = null;
  let lastTapAt = 0;
  let lastTapSide: "left" | "right" | null = null;

  function resetLastTap() {
    lastTapAt = 0;
    lastTapSide = null;
  }

  function handleTouchStart(event: TouchEvent) {
    if (event.touches.length !== 1 || isPlayerControl(event.target)) {
      touchStart = null;
      resetLastTap();
      return;
    }

    const touch = event.touches[0];

    touchStart = {
      clientX: touch.clientX,
      clientY: touch.clientY,
      startedAt: window.performance.now(),
    };
  }

  function handleTouchEnd(event: TouchEvent) {
    const start = touchStart;
    touchStart = null;

    if (
      !start
      || event.changedTouches.length !== 1
      || isPlayerControl(event.target)
    ) {
      resetLastTap();
      return;
    }

    const touch = event.changedTouches[0];
    const touchDuration = window.performance.now() - start.startedAt;
    const touchDistance = Math.hypot(
      touch.clientX - start.clientX,
      touch.clientY - start.clientY,
    );

    if (touchDuration > 250 || touchDistance > 10) {
      resetLastTap();
      return;
    }

    const bounds = element.getBoundingClientRect();
    const tapSide =
      touch.clientX < bounds.left + bounds.width / 2 ? "left" : "right";
    const tappedAt = window.performance.now();
    const isDoubleTap =
      tapSide === lastTapSide
      && tappedAt - lastTapAt <= 300;

    if (!isDoubleTap) {
      lastTapAt = tappedAt;
      lastTapSide = tapSide;
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    resetLastTap();

    const seconds = tapSide === "left" ? -10 : 10;

    if (seekPlayerBy(player, seconds)) {
      player.userActive(true);
      onDoubleTapSeek(seconds);
    }
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
      return;
    }

    const target = event.target;

    if (
      target instanceof HTMLElement
      && target.closest(
        "input, textarea, select, [contenteditable='true'], [role='slider']",
      )
    ) {
      return;
    }

    if (event.key === "ArrowLeft") {
      event.preventDefault();
      seekPlayerBy(player, -10);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      seekPlayerBy(player, 10);
    }
  }

  window.addEventListener("keydown", handleKeyDown);

  if (element instanceof HTMLElement) {
    element.addEventListener("touchstart", handleTouchStart, {
      capture: true,
      passive: true,
    });
    element.addEventListener("touchend", handleTouchEnd, {
      capture: true,
      passive: false,
    });
  }

  return () => {
    window.removeEventListener("keydown", handleKeyDown);

    if (element instanceof HTMLElement) {
      element.removeEventListener("touchstart", handleTouchStart, true);
      element.removeEventListener("touchend", handleTouchEnd, true);
    }
  };
}
