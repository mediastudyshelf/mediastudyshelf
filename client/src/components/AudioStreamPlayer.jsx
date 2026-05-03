import { useRef, useEffect, useState } from 'react';
import Hls from 'hls.js';
import { prepareHls, heartbeatHls } from '../lib/api';

const HEARTBEAT_INTERVAL = 5_000;

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
  const barRef = useRef(null);
  const [progress, setProgress] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [displayDuration, setDisplayDuration] = useState(
    audio.duration_seconds ? formatDuration(audio.duration_seconds) : ''
  );
  const [loading, setLoading] = useState(false);

  // Session recovery
  const [sessionRevision, setSessionRevision] = useState(0);
  const resumeTimeRef = useRef(null);

  // Start HLS session only when user clicks play (isPlaying becomes true)
  useEffect(() => {
    if (!isPlaying) return;

    const el = audioRef.current;
    if (!el) return;

    const abortController = new AbortController();
    const isRecovery = resumeTimeRef.current != null;

    setLoading(true);

    // Tear down previous
    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
    sessionIdRef.current = null;

    if (!isRecovery) {
      el.removeAttribute('src');
      el.load();
      el.currentTime = 0;
      setProgress(0);
      setElapsedSeconds(0);
    }

    const startPosition = isRecovery ? resumeTimeRef.current : 0;
    resumeTimeRef.current = null;

    prepareHls(audio.url, abortController.signal, startPosition).then(result => {
      if (abortController.signal.aborted) return;

      if (!result) {
        // Fallback to direct URL
        el.src = audio.url;
        setLoading(false);
        el.play().catch(() => {});
        return;
      }

      sessionIdRef.current = result.id;

      // Heartbeat — detect session death with guard against stale sessions
      const currentSessionId = result.id;
      heartbeatRef.current = setInterval(async () => {
        if (abortController.signal.aborted || !heartbeatRef.current) return;
        // Guard against stale closures after session recovery
        if (sessionIdRef.current !== currentSessionId) {
          clearInterval(heartbeatRef.current);
          heartbeatRef.current = null;
          return;
        }
        const alive = await heartbeatHls(currentSessionId, el.currentTime || 0);
        if (!alive && !abortController.signal.aborted) {
          // Stop heartbeat, trigger recovery
          clearInterval(heartbeatRef.current);
          heartbeatRef.current = null;
          resumeTimeRef.current = el.currentTime || 0;
          setSessionRevision(r => r + 1);
        }
      }, HEARTBEAT_INTERVAL);

      if (Hls.isSupported()) {
        const hls = new Hls({
          startPosition,
          maxBufferLength: 30,
          maxMaxBufferLength: 60,
          manifestLoadingTimeOut: 10000,
          manifestLoadingMaxRetry: 3,
          levelLoadingTimeOut: 10000,
          levelLoadingMaxRetry: 3,
          fragLoadingTimeOut: 30000,
          fragLoadingMaxRetry: 5,
          fragLoadingRetryDelay: 500,
          // Audio-only streams work better with these settings
          maxBufferSize: 0,
          maxBufferLength: 10,
          liveSyncDurationCount: 1,
        });
        hlsRef.current = hls;

        // Handle errors with retry logic
        hls.on(Hls.Events.ERROR, (event, data) => {
          if (abortController.signal.aborted) return;
          
          if (data.fatal) {
            console.error('Fatal HLS error:', data.type, data.details);
            // Try to recover
            if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
              console.log('Attempting to recover from network error...');
              hls.startLoad();
            } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
              console.log('Attempting to recover from media error...');
              hls.recoverMediaError();
            } else {
              // Unrecoverable error - trigger session recovery
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
            // Non-fatal error - log but continue
            console.warn('HLS non-fatal error:', data.type, data.details);
          }
        });

        hls.loadSource(result.url);
        hls.attachMedia(el);
        
        // Wait for manifest to be parsed before considering ready
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          if (!abortController.signal.aborted) {
            setLoading(false);
            // Only auto-play if we're still in playing state
            if (isPlaying) {
              el.play().catch(() => {});
            }
          }
        });
      } else if (el.canPlayType('application/vnd.apple.mpegurl')) {
        el.src = result.url;
        if (startPosition > 0) el.currentTime = startPosition;
        el.addEventListener('canplay', () => {
          setLoading(false);
          el.play().catch(() => {});
        }, { once: true });
      } else {
        // Fallback
        el.src = audio.url;
        setLoading(false);
        el.play().catch(() => {});
      }
    }).catch(() => {
      setLoading(false);
    });

    return () => {
      abortController.abort();
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
      sessionIdRef.current = null;
    };
  }, [isPlaying, audio.url, sessionRevision]);

  // Cleanup when paused (stop heartbeats but keep resume position)
  useEffect(() => {
    if (!isPlaying) {
      const el = audioRef.current;
      if (el) {
        el.pause();
      }
      // Keep session alive briefly for resume, but stop heartbeat
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
    }
  }, [isPlaying]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
      sessionIdRef.current = null;
    };
  }, []);

  // Reset state when audio file changes
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
      // Store current time for resume when paused
      const el = audioRef.current;
      if (el) {
        resumeTimeRef.current = el.currentTime;
      }
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
