import { useRef, useEffect, useState } from 'react';
import Hls from 'hls.js';
import { prepareHls, heartbeatHls } from '../lib/api';

const HEARTBEAT_INTERVAL = 5_000;
// How long after a pause we keep the streaming session alive (heartbeats keep
// firing) so a quick resume is instant. After this, we drop the session and
// the server's gc reaps it; the next play re-prepares from el.currentTime.
const PAUSE_GRACE_MS = 5 * 60 * 1000;

function formatDuration(seconds) {
  if (seconds == null) return '';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function AudioStreamPlayer({ audio, isPlaying, onPlay, onPause }) {
  const audioRef = useRef(null);
  const hlsRef = useRef(null);
  const sessionIdRef = useRef(null);
  const heartbeatRef = useRef(null);
  const pauseGraceTimerRef = useRef(null);
  const abortControllerRef = useRef(null);
  const barRef = useRef(null);
  const [progress, setProgress] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [displayDuration, setDisplayDuration] = useState(
    audio.duration_seconds ? formatDuration(audio.duration_seconds) : ''
  );
  const [loading, setLoading] = useState(false);

  // Session recovery (forced re-prepare from current position)
  const [sessionRevision, setSessionRevision] = useState(0);
  const resumeTimeRef = useRef(null);

  // Drop the streaming session entirely (used on track change, unmount, or
  // when the pause grace timer expires). Audio element is left intact.
  const teardownSession = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }
    if (pauseGraceTimerRef.current) {
      clearTimeout(pauseGraceTimerRef.current);
      pauseGraceTimerRef.current = null;
    }
    sessionIdRef.current = null;
  };

  // Prepare a server session, attach HLS, start heartbeat. Called when the
  // user hits play and there's no active session (first play, or after grace
  // expired, or after a recovery).
  const setupSession = () => {
    const el = audioRef.current;
    if (!el) return;

    setLoading(true);

    const startPosition = resumeTimeRef.current ?? 0;
    resumeTimeRef.current = null;

    if (startPosition === 0) {
      el.removeAttribute('src');
      el.load();
      el.currentTime = 0;
      setProgress(0);
      setElapsedSeconds(0);
    }

    const abort = new AbortController();
    abortControllerRef.current = abort;

    prepareHls(audio.url, abort.signal, startPosition).then(result => {
      if (abort.signal.aborted) return;

      if (!result) {
        // Fallback to direct URL
        el.src = audio.url;
        setLoading(false);
        el.play().catch(() => {});
        return;
      }

      const sid = result.id;
      sessionIdRef.current = sid;

      heartbeatRef.current = setInterval(async () => {
        if (abort.signal.aborted || !heartbeatRef.current) return;
        // Stale-closure guard: if a recovery rotated the session id, stop.
        if (sessionIdRef.current !== sid) {
          clearInterval(heartbeatRef.current);
          heartbeatRef.current = null;
          return;
        }
        const alive = await heartbeatHls(sid, el.currentTime || 0);
        if (!alive && !abort.signal.aborted) {
          // Server says it doesn't know this session anymore — recover.
          clearInterval(heartbeatRef.current);
          heartbeatRef.current = null;
          resumeTimeRef.current = el.currentTime || 0;
          setSessionRevision(r => r + 1);
        }
      }, HEARTBEAT_INTERVAL);

      if (Hls.isSupported()) {
        const hls = new Hls({
          startPosition,
          maxMaxBufferLength: 60,
          manifestLoadingTimeOut: 10000,
          manifestLoadingMaxRetry: 3,
          levelLoadingTimeOut: 10000,
          levelLoadingMaxRetry: 3,
          fragLoadingTimeOut: 30000,
          fragLoadingMaxRetry: 5,
          fragLoadingRetryDelay: 500,
          maxBufferSize: 0,
          maxBufferLength: 10,
          liveSyncDurationCount: 1,
        });
        hlsRef.current = hls;

        hls.on(Hls.Events.ERROR, (event, data) => {
          if (abort.signal.aborted) return;
          if (data.fatal) {
            console.error('Fatal HLS error:', data.type, data.details);
            if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
              hls.startLoad();
            } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
              hls.recoverMediaError();
            } else {
              // Unrecoverable — drop the session and trigger a recovery.
              hls.destroy();
              hlsRef.current = null;
              if (heartbeatRef.current) {
                clearInterval(heartbeatRef.current);
                heartbeatRef.current = null;
              }
              resumeTimeRef.current = el.currentTime || 0;
              setSessionRevision(r => r + 1);
            }
          } else {
            console.warn('HLS non-fatal error:', data.type, data.details);
          }
        });

        hls.loadSource(result.url);
        hls.attachMedia(el);

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          if (abort.signal.aborted) return;
          setLoading(false);
          if (isPlaying) el.play().catch(() => {});
        });
      } else if (el.canPlayType('application/vnd.apple.mpegurl')) {
        el.src = result.url;
        if (startPosition > 0) el.currentTime = startPosition;
        el.addEventListener('canplay', () => {
          setLoading(false);
          el.play().catch(() => {});
        }, { once: true });
      } else {
        el.src = audio.url;
        setLoading(false);
        el.play().catch(() => {});
      }
    }).catch(() => {
      setLoading(false);
    });
  };

  // Track change or forced recovery → drop the session entirely. Setup runs
  // on the next play. Also covers unmount (cleanup fires on dep change OR
  // component teardown).
  useEffect(() => {
    return () => {
      teardownSession();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audio.url, sessionRevision]);

  // Play/pause control. This effect never destroys the session on its own
  // (the pause grace timer does, after PAUSE_GRACE_MS).
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;

    if (isPlaying) {
      // Cancel a pending pause-grace teardown, if any.
      if (pauseGraceTimerRef.current) {
        clearTimeout(pauseGraceTimerRef.current);
        pauseGraceTimerRef.current = null;
      }
      if (sessionIdRef.current) {
        // Reuse the live session — instant resume.
        el.play().catch(() => {});
      } else {
        // First play, or grace already expired.
        setupSession();
      }
    } else {
      el.pause();
      // Arm the grace timer; if no resume within PAUSE_GRACE_MS, drop the
      // session so the server can gc it.
      if (sessionIdRef.current && !pauseGraceTimerRef.current) {
        pauseGraceTimerRef.current = setTimeout(() => {
          resumeTimeRef.current = el.currentTime || 0;
          teardownSession();
        }, PAUSE_GRACE_MS);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying]);

  // Reset display state when audio file changes
  useEffect(() => {
    setProgress(0);
    setElapsedSeconds(0);
    resumeTimeRef.current = null;
    setDisplayDuration(audio.duration_seconds ? formatDuration(audio.duration_seconds) : '');
  }, [audio.url, audio.duration_seconds]);

  const handleTimeUpdate = () => {
    const el = audioRef.current;
    if (!el || !el.duration) return;
    setProgress(el.currentTime / el.duration);
    setElapsedSeconds(el.currentTime);
  };

  const handleLoadedMetadata = () => {
    const el = audioRef.current;
    if (el && el.duration && isFinite(el.duration)) {
      setDisplayDuration(formatDuration(Math.round(el.duration)));
    }
  };

  const handleEnded = () => {
    setProgress(0);
    setElapsedSeconds(0);
    onPause();
  };

  const handleBarClick = (e) => {
    const el = audioRef.current;
    const bar = barRef.current;
    if (!el || !bar || !el.duration) return;
    const rect = bar.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    el.currentTime = ratio * el.duration;
    setProgress(ratio);
    if (!isPlaying) onPlay();
  };

  const togglePlay = () => {
    if (isPlaying) {
      onPause();
    } else {
      onPlay();
    }
  };

  return (
    <div className="asset-row asset-row--audio">
      <button
        className={`audio-play-btn${isPlaying ? ' audio-play-btn--playing' : ''}`}
        onClick={togglePlay}
        disabled={loading}
      >
        {loading ? (
          <span className="audio-spinner" />
        ) : isPlaying ? (
          '❚❚'
        ) : (
          '▶'
        )}
      </button>
      <div className="audio-row__body">
        <div className="audio-row__top">
          <span className="asset-row__filename">{audio.label}</span>
          <span className="audio-row__duration">
            {formatDuration(elapsedSeconds)}{displayDuration ? ` / ${displayDuration}` : ''}
          </span>
        </div>
        <div className="audio-bar" ref={barRef} onClick={handleBarClick}>
          <div
            className={`audio-bar__fill${isPlaying ? ' audio-bar__fill--active' : ''}`}
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      </div>
      <audio
        ref={audioRef}
        preload="metadata"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
      />
    </div>
  );
}
