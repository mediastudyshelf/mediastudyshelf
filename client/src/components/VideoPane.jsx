import { useRef, useEffect, useState } from 'react';
import Hls from 'hls.js';
import { prepareHls, heartbeatHls } from '../lib/api';

const HEARTBEAT_INTERVAL = 5_000; // 5 seconds — frequent enough for buffer management

export default function VideoPane({ videos, activeVideoUrl, onVideoSelect, expanded, hidden, height }) {
  const videoRef = useRef(null);
  const hlsRef = useRef(null);
  const sessionIdRef = useRef(null);
  const menuRef = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const activeVideo = videos?.find(v => v.url === activeVideoUrl) || videos?.[0];
  const mediaUrl = activeVideo?.url;

  // Request HLS, attach player, run heartbeat with playhead
  useEffect(() => {
    const el = videoRef.current;
    if (!el || !mediaUrl) return;

    let cancelled = false;
    let heartbeatTimer = null;

    // Tear down previous HLS instance and reset video element
    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }
    sessionIdRef.current = null;
    el.removeAttribute('src');
    el.load();
    el.currentTime = 0;

    prepareHls(mediaUrl).then(result => {
      if (cancelled) return;

      if (!result) {
        el.src = mediaUrl;
        return;
      }

      sessionIdRef.current = result.id;

      // Heartbeat sends current playhead position
      heartbeatTimer = setInterval(() => {
        const currentTime = el.currentTime || 0;
        heartbeatHls(result.id, currentTime);
      }, HEARTBEAT_INTERVAL);

      if (Hls.isSupported()) {
        const hls = new Hls({ startPosition: 0 });
        hlsRef.current = hls;
        hls.loadSource(result.url);
        hls.attachMedia(el);
      } else if (el.canPlayType('application/vnd.apple.mpegurl')) {
        el.src = result.url;
      } else {
        el.src = mediaUrl;
      }
    });

    return () => {
      cancelled = true;
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
      sessionIdRef.current = null;
    };
  }, [mediaUrl]);

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
      <video
        ref={videoRef}
        className="video-pane__player"
        controls
        preload="metadata"
      />
    </div>
  );
}
