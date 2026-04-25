import { useRef, useEffect, useState } from 'react';

export default function VideoPane({ videos, activeVideoUrl, onVideoSelect, expanded, hidden }) {
  const videoRef = useRef(null);
  const menuRef = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const activeVideo = videos?.find(v => v.url === activeVideoUrl) || videos?.[0];

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

  if (!videos || videos.length === 0) {
    return (
      <div className={className}>
        <span className="video-pane__label">VIDEO</span>
        <div className="video-pane__empty">No video available</div>
      </div>
    );
  }

  const hasMultiple = videos.length > 1;
  const activeIndex = videos.findIndex(v => v.url === activeVideoUrl) + 1;

  return (
    <div className={className}>
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
        src={activeVideo?.url}
        controls
        preload="metadata"
      />
    </div>
  );
}
