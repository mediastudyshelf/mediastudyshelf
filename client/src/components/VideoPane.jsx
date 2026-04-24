import { useRef, useEffect } from 'react';

export default function VideoPane({ videoUrl, expanded, hidden }) {
  const videoRef = useRef(null);

  // Pause video when hidden
  useEffect(() => {
    if (hidden && videoRef.current && !videoRef.current.paused) {
      videoRef.current.pause();
    }
  }, [hidden]);

  const className = [
    'video-pane',
    expanded && 'video-pane--expanded',
    hidden && 'video-pane--hidden',
  ].filter(Boolean).join(' ');

  if (!videoUrl) {
    return (
      <div className={className}>
        <span className="video-pane__label">VIDEO</span>
        <div className="video-pane__empty">No video available</div>
      </div>
    );
  }

  return (
    <div className={className}>
      <span className="video-pane__label">VIDEO</span>
      <video
        ref={videoRef}
        className="video-pane__player"
        src={videoUrl}
        controls
        preload="metadata"
      />
    </div>
  );
}
