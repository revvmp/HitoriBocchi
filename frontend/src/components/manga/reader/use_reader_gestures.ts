"use client";

import { useRef, type MouseEvent, type TouchEvent } from "react";

import { isReaderControlTarget } from "@/components/manga/reader/reader_settings";

type Point = {
  x: number;
  y: number;
};

type TimedPoint = Point & {
  time: number;
};

// A double-click or double-tap on the pages toggles the reader controls.
export function useReaderControlsToggle(toggleReaderControls: () => void) {
  const readerTouchStartRef = useRef<TimedPoint | null>(null);
  const lastReaderTapRef = useRef<TimedPoint | null>(null);
  const lastTouchControlsToggleAtRef = useRef(0);

  function handleReaderDoubleClick(event: MouseEvent<HTMLElement>) {
    if (
      isReaderControlTarget(event.target)
      || Date.now() - lastTouchControlsToggleAtRef.current < 700
    ) {
      return;
    }

    toggleReaderControls();
  }

  function handleReaderTouchStart(event: TouchEvent<HTMLElement>) {
    if (isReaderControlTarget(event.target)) {
      readerTouchStartRef.current = null;
      return;
    }

    const touch = event.touches[0];
    if (!touch) {
      return;
    }

    readerTouchStartRef.current = {
      time: Date.now(),
      x: touch.clientX,
      y: touch.clientY,
    };
  }

  function handleReaderTouchEnd(event: TouchEvent<HTMLElement>) {
    const touchStart = readerTouchStartRef.current;
    const touch = event.changedTouches[0];
    readerTouchStartRef.current = null;

    if (!touchStart || !touch || isReaderControlTarget(event.target)) {
      return;
    }

    const now = Date.now();
    const movedDistance = Math.hypot(
      touch.clientX - touchStart.x,
      touch.clientY - touchStart.y,
    );
    if (now - touchStart.time > 300 || movedDistance > 24) {
      lastReaderTapRef.current = null;
      return;
    }

    const lastTap = lastReaderTapRef.current;
    if (
      lastTap
      && now - lastTap.time < 350
      && Math.hypot(touch.clientX - lastTap.x, touch.clientY - lastTap.y) < 48
    ) {
      event.preventDefault();
      lastReaderTapRef.current = null;
      lastTouchControlsToggleAtRef.current = now;
      toggleReaderControls();
      return;
    }

    lastReaderTapRef.current = {
      time: now,
      x: touch.clientX,
      y: touch.clientY,
    };
  }

  return {
    onDoubleClick: handleReaderDoubleClick,
    onTouchEndCapture: handleReaderTouchEnd,
    onTouchStartCapture: handleReaderTouchStart,
  };
}

// In the paged reader, swiping right advances and swiping left goes back.
export function usePagedSwipe(goToNextPage: () => void, goToPreviousPage: () => void) {
  const touchStartRef = useRef<Point | null>(null);

  function handlePagedTouchStart(event: TouchEvent<HTMLElement>) {
    const touch = event.touches[0];

    if (touch) {
      touchStartRef.current = {
        x: touch.clientX,
        y: touch.clientY,
      };
    }
  }

  function handlePagedTouchEnd(event: TouchEvent<HTMLElement>) {
    const touch = event.changedTouches[0];
    const touchStart = touchStartRef.current;
    touchStartRef.current = null;

    if (!touch || !touchStart) {
      return;
    }

    const horizontalDistance = touch.clientX - touchStart.x;
    const verticalDistance = touch.clientY - touchStart.y;

    if (
      Math.abs(horizontalDistance) < 50
      || Math.abs(horizontalDistance) <= Math.abs(verticalDistance)
    ) {
      return;
    }

    if (horizontalDistance > 0) {
      goToNextPage();
    } else {
      goToPreviousPage();
    }
  }

  return {
    onTouchEnd: handlePagedTouchEnd,
    onTouchStart: handlePagedTouchStart,
  };
}
