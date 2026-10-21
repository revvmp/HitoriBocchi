import type Hls from "hls.js";

export const MOBILE_HLS_TYPE = "application/x-hitoribocchi-hls";

type HlsConstructor = typeof Hls;
type Source = { src: string; type?: string; externalSubtitles?: boolean };
type Html5Tech = {
  el: () => HTMLVideoElement;
  error: (error: { code: number; message: string }) => void;
};
type SourceHandler = {
  canHandleSource: (source: Source) => string;
  canPlayType: (type: string) => string;
  handleSource: (source: Source, tech: Html5Tech) => { dispose: () => void };
};
type Html5Constructor = {
  registerSourceHandler: (handler: SourceHandler, index: number) => void;
};
type WirelessVideo = HTMLVideoElement & {
  webkitCurrentPlaybackTargetIsWireless?: boolean;
};

const registeredTechs = new WeakSet<Html5Constructor>();

export function isMobileHlsSource(src: string, origin: string, isMobile: boolean) {
  if (!isMobile) {
    return false;
  }

  const url = new URL(src, origin);

  return url.origin === origin
    && /^\/api\/(?:anidb-streams|anizone-streams|playback-streams)\//.test(url.pathname)
    && url.pathname.toLowerCase().endsWith(".m3u8");
}

export function attachMobileHls(video: WirelessVideo, src: string, HlsClass: HlsConstructor, reportError: Html5Tech["error"], externalSubtitles = false) {
  const hls = new HlsClass({
    enableWorker: true,
    // Use MSE where available; hls.js falls back to MMS on newer iPhones.
    preferManagedMediaSource: false,
    backBufferLength: 30,
    // Video.js owns external subtitles, including the native fullscreen bridge.
    enableWebVTT: !externalSubtitles,
    enableIMSC1: !externalSubtitles,
    enableCEA708Captions: !externalSubtitles,
  });
  const previousRemotePlayback = video.disableRemotePlayback;
  const nativeSource = document.createElement("source");
  nativeSource.src = src;
  nativeSource.type = "application/vnd.apple.mpegurl";
  let disposed = false;
  let destroyed = false;
  let recoveredMediaError = false;
  let resumeNative: (() => void) | undefined;

  function destroyHls() {
    if (!destroyed) {
      destroyed = true;
      hls.destroy();
      nativeSource.remove();
      video.disableRemotePlayback = previousRemotePlayback;
    }
  }

  function fallBackToNative(code: number) {
    const currentTime = video.currentTime;
    const wasPlaying = !video.paused;
    destroyHls();

    if (!video.canPlayType("application/vnd.apple.mpegurl")) {
      reportError({ code, message: "Unable to play this stream. Try another server." });
      return;
    }

    resumeNative = () => {
      resumeNative = undefined;

      if (disposed) {
        return;
      }

      if (currentTime > 0 && Number.isFinite(video.duration)) {
        video.currentTime = Math.min(currentTime, Math.max(0, video.duration - 0.1));
      }

      if (wasPlaying) {
        void video.play().catch(() => {});
      }
    };
    video.addEventListener("loadedmetadata", resumeNative, { once: true });
    video.src = src;
    video.load();
  }

  function handleWirelessPlayback() {
    if (!disposed && !destroyed && video.webkitCurrentPlaybackTargetIsWireless) {
      fallBackToNative(3);
    }
  }

  hls.on(HlsClass.Events.MEDIA_ATTACHING, () => {
    if (disposed || destroyed || !video.canPlayType("application/vnd.apple.mpegurl")) {
      return;
    }

    // MMS needs either remote playback disabled or a native alternative for AirPlay.
    // The internal buffer controller attaches first and may remove source children.
    video.appendChild(nativeSource);
    video.disableRemotePlayback = previousRemotePlayback;
  });
  hls.on(HlsClass.Events.ERROR, (_event, data) => {
    if (disposed || destroyed || !data.fatal) {
      return;
    }

    if (data.type === HlsClass.ErrorTypes.MEDIA_ERROR && !recoveredMediaError) {
      recoveredMediaError = true;
      hls.recoverMediaError();
      return;
    }

    // Fatal network errors arrive after the library exhausts its own retries.
    fallBackToNative(data.type === HlsClass.ErrorTypes.NETWORK_ERROR ? 2 : 3);
  });
  video.addEventListener("webkitcurrentplaybacktargetiswirelesschanged", handleWirelessPlayback);
  hls.loadSource(src);
  hls.attachMedia(video);

  return {
    dispose() {
      disposed = true;
      video.removeEventListener("webkitcurrentplaybacktargetiswirelesschanged", handleWirelessPlayback);

      if (resumeNative) {
        video.removeEventListener("loadedmetadata", resumeNative);
      }

      destroyHls();
    },
  };
}

export function registerMobileHls(Html5: unknown, HlsClass: HlsConstructor) {
  if (
    (typeof Html5 !== "function" && typeof Html5 !== "object")
    || Html5 === null
    || !("registerSourceHandler" in Html5)
    || typeof Html5.registerSourceHandler !== "function"
  ) {
    return false;
  }

  const tech = Html5 as Html5Constructor;

  if (registeredTechs.has(tech)) {
    return true;
  }

  function canPlayType(type: string) {
    return type === MOBILE_HLS_TYPE && HlsClass.isSupported() ? "probably" : "";
  }

  tech.registerSourceHandler({
    canHandleSource: (source) => canPlayType(source.type || ""),
    canPlayType,
    handleSource: (source, tech) => attachMobileHls(tech.el(), source.src, HlsClass, (error) => tech.error(error), source.externalSubtitles),
  }, 0);
  registeredTechs.add(tech);
  return true;
}
