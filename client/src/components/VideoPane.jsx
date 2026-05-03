import { useRef, useEffect, useState } from 'react';
import Hls from 'hls.js';
import { prepareHls, heartbeatHls } from '../lib/api';

const HEARTBEAT_INTERVAL = 5_000;

export default function VideoPane({ videos, activeVideoUrl, onVideoSelect, expanded, hidden, height }) {
  const videoRef = useRef(null);
  const hlsRef = useRef(null);
  const sessionIdRef = useRef(null);
  const heartbeatRef = useRef(null);
  const menuRef = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMessage, setLoadingMessage] = useState('Preparing video...');

  // Increment to trigger session recovery
  const [sessionRevision, setSessionRevision] = useState(0);
  const resumeTimeRef = useRef(null);

  const activeVideo = videos?.find(v => v.url === activeVideoUrl) || videos?.[0];
  const mediaUrl = activeVideo?.url;

  // Main effect: start HLS session (runs on mediaUrl change or recovery)
  useEffect(() => {
    const el = videoRef.current;
    if (!el || !mediaUrl) return;

    const abortController = new AbortController();
    const isRecovery = resumeTimeRef.current != null;

    setLoading(true);
    setLoadingMessage(isRecovery ? 'Recovering session...' : 'Preparing video...');

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
    }

    const startPosition = isRecovery ? resumeTimeRef.current : 0;
    resumeTimeRef.current = null;

    prepareHls(mediaUrl, abortController.signal, startPosition).then(result => {
      if (abortController.signal.aborted) return;

      if (!result) {
        el.src = mediaUrl;
        setLoading(false);
        return;
      }

      sessionIdRef.current = result.id;

      // Heartbeat — detect session death
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
          // Stop heartbeat, trigger recovery via state
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
        hls.on(Hls.Events.FRAG_BUFFERED, () => {
          if (!abortController.signal.aborted) setLoading(false);
        });
      } else if (el.canPlayType('application/vnd.apple.mpegurl')) {
        el.src = result.url;
        if (startPosition > 0) el.currentTime = startPosition;
        el.addEventListener('canplay', () => setLoading(false), { once: true });
      } else {
        el.src = mediaUrl;
        setLoading(false);
      }
    }).catch(() => {});

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
  }, [mediaUrl, sessionRevision]);

  // Pause video when hidden
  useEffect(() => {
    if (hidden && videoRef.current && !videoRef.current.paused) {
      videoRef.current.pause();
    }
  }, [hidden]);

  // Click-outside to close menu
  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  const className = [
    'video-pane',
    expanded && 'video-pane--expanded',
    hidden && 'video-pane--hidden',
  ].filter(Boolean).join(' ');

  const style = height && !expanded && !hidden ? { height } : undefined;

  if (!videos || videos.length === 0) {
    return (
      <div className={className} style={style}>
        <span className="video-pane__label">VIDEO</span>
        <div className="video-pane__empty">No video available</div>
      </div>
    );
  }

  const hasMultiple = videos.length > 1;
  const activeIndex = videos.findIndex(v => v.url === activeVideoUrl) + 1;

  return (
    <div className={className} style={style}>
      <div className="video-pane__header">
        <span className="video-pane__label">VIDEO</span>
        {hasMultiple && (
          <div className="video-selector-wrap" ref={menuRef}>
            <button
              className="video-selector"
              onClick={() => setMenuOpen(o => !o)}
            >
              <span className="video-selector__filename">{activeVideo?.filename}</span>
              <span className="video-selector__counter">{activeIndex} of {videos.length}</span>
              <span className="video-selector__chevron">{menuOpen ? '▴' : '▾'}</span>
            </button>

            {menuOpen && (
              <div className="video-menu">
                {videos.map(vid => {
                  const isActive = vid.url === activeVideoUrl;
                  return (
                    <button
                      key={vid.url}
                      className={`video-menu__item${isActive ? ' video-menu__item--active' : ''}`}
                      onClick={() => { onVideoSelect(vid.url); setMenuOpen(false); }}
                    >
                      <span className="video-menu__filename">{vid.filename}</span>
                      {isActive && <span className="video-menu__check">✓</span>}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
      {loading && (
        <div className="video-pane__loading">
          <div className="video-pane__spinner" />
          <span>{loadingMessage}</span>
        </div>
      )}
      <video
        ref={videoRef}
        className="video-pane__player"
        controls
        preload="metadata"
        style={loading ? { display: 'none' } : undefined}
      />
    </div>
  );
}
