type SubtitleTrack = {
  mode: string;
};

type PresentationMode = "inline" | "fullscreen" | "picture-in-picture";

export function bridgeNativeFullscreenSubtitles(video: HTMLVideoElement, subtitleSrc: string, getInlineTrack: () => SubtitleTrack | undefined) {
  if (!("webkitEnterFullscreen" in video)) {
    return () => {};
  }

  // Add this after tech initialization so Video.js does not ingest a duplicate.
  const nativeElement = document.createElement("track");
  nativeElement.kind = "subtitles";
  nativeElement.label = "English";
  nativeElement.srclang = "en";
  nativeElement.src = subtitleSrc;
  video.appendChild(nativeElement);

  const nativeTrack = nativeElement.track;
  let presentation: PresentationMode = "inline";
  let subtitlesEnabled = getInlineTrack()?.mode === "showing";
  let recoveryPending = false;
  let selectionTimer: ReturnType<typeof setTimeout> | undefined;
  const nativeVideo = video as HTMLVideoElement & {
    webkitDisplayingFullscreen?: boolean;
    webkitPresentationMode?: PresentationMode;
  };

  // Hidden tracks preload their cues without displaying native captions inline.
  nativeTrack.mode = "hidden";

  function readPresentation(): PresentationMode {
    if (document.pictureInPictureElement === video) {
      return "picture-in-picture";
    }
    return nativeVideo.webkitPresentationMode
      ?? (nativeVideo.webkitDisplayingFullscreen === undefined
        ? presentation
        : nativeVideo.webkitDisplayingFullscreen ? "fullscreen" : "inline");
  }

  function cancelSelection() {
    clearTimeout(selectionTimer);
    selectionTimer = undefined;
  }

  function applyRendering(refreshNative = false) {
    const inlineTrack = getInlineTrack();

    if (presentation !== "inline") {
      if (inlineTrack) {
        inlineTrack.mode = "hidden";
      }
      // Re-select the track when Safari moves its native caption renderer.
      if (refreshNative && subtitlesEnabled) {
        nativeTrack.mode = "hidden";
      }
      nativeTrack.mode = subtitlesEnabled ? "showing" : "hidden";
    } else {
      nativeTrack.mode = "hidden";
      if (inlineTrack) {
        inlineTrack.mode = subtitlesEnabled ? "showing" : "disabled";
      }
    }
  }

  function setPresentation(next: PresentationMode) {
    cancelSelection();
    if (presentation === "inline" && !recoveryPending) {
      subtitlesEnabled = getInlineTrack()?.mode === "showing";
    }
    presentation = next;
    applyRendering(true);
  }

  function handleNativeTrackChange() {
    const next = readPresentation();
    if (next !== presentation) {
      setPresentation(next);
      return;
    }

    if (presentation === "inline") {
      if (nativeTrack.mode === "showing") {
        nativeTrack.mode = "hidden";
      }
      return;
    }

    cancelSelection();
    if (document.hidden || recoveryPending) {
      return;
    }
    // Let presentation/visibility events settle before accepting a native menu
    // selection. Track resets during PiP transitions are not a subtitle choice.
    const previous = presentation;
    selectionTimer = setTimeout(() => {
      selectionTimer = undefined;
      if (!document.hidden && !recoveryPending && presentation === previous && readPresentation() === previous) {
        subtitlesEnabled = nativeTrack.mode === "showing";
      }
    }, 0);
  }

  function handleBeginFullscreen() {
    setPresentation("fullscreen");
  }

  function handleEndFullscreen() {
    const next = readPresentation();
    setPresentation(nativeVideo.webkitPresentationMode ?? (next === "picture-in-picture" ? next : "inline"));
  }

  function handlePresentationChange() {
    setPresentation(readPresentation());
  }

  function handleEnterPictureInPicture() {
    setPresentation("picture-in-picture");
  }

  function handleLeavePictureInPicture() {
    const next = readPresentation();
    setPresentation(nativeVideo.webkitPresentationMode ?? (next === "fullscreen" ? next : "inline"));
  }

  function handleResume() {
    if (document.hidden) {
      cancelSelection();
      if (presentation === "inline" && !recoveryPending) {
        subtitlesEnabled = getInlineTrack()?.mode === "showing";
      }
      recoveryPending = true;
      return;
    }

    const next = readPresentation();
    if (recoveryPending || next !== presentation) {
      setPresentation(next);
      recoveryPending = false;
    }
  }

  video.addEventListener("webkitbeginfullscreen", handleBeginFullscreen);
  video.addEventListener("webkitendfullscreen", handleEndFullscreen);
  video.addEventListener("webkitpresentationmodechanged", handlePresentationChange);
  video.addEventListener("enterpictureinpicture", handleEnterPictureInPicture);
  video.addEventListener("leavepictureinpicture", handleLeavePictureInPicture);
  video.textTracks.addEventListener("change", handleNativeTrackChange);
  document.addEventListener("visibilitychange", handleResume);
  window.addEventListener("pageshow", handleResume);
  video.addEventListener("playing", handleResume);

  handlePresentationChange();

  return () => {
    cancelSelection();
    video.removeEventListener("webkitbeginfullscreen", handleBeginFullscreen);
    video.removeEventListener("webkitendfullscreen", handleEndFullscreen);
    video.removeEventListener("webkitpresentationmodechanged", handlePresentationChange);
    video.removeEventListener("enterpictureinpicture", handleEnterPictureInPicture);
    video.removeEventListener("leavepictureinpicture", handleLeavePictureInPicture);
    video.textTracks.removeEventListener("change", handleNativeTrackChange);
    document.removeEventListener("visibilitychange", handleResume);
    window.removeEventListener("pageshow", handleResume);
    video.removeEventListener("playing", handleResume);
    nativeTrack.mode = "disabled";
    nativeElement.remove();
  };
}
