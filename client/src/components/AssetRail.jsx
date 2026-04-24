import { useRef, useEffect, useState, useCallback } from 'react';

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function formatDuration(seconds) {
  if (seconds == null) return '';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function fileExtension(filename) {
  const dot = filename.lastIndexOf('.');
  return dot >= 0 ? filename.slice(dot + 1).toUpperCase() : '';
}

// ── Document row ────────────────────────────────────────────────

function DocumentRow({ pdf, onPdfSelect }) {
  return (
    <button className="asset-row asset-row--doc" onClick={() => onPdfSelect(pdf.url)}>
      <span className="asset-icon asset-icon--pdf">PDF</span>
      <div className="asset-row__info">
        <span className="asset-row__filename">{pdf.filename}</span>
        <span className="asset-row__meta">
          {pdf.pages != null ? `${pdf.pages} pages` : ''}
          {pdf.pages != null && pdf.size_bytes ? ' · ' : ''}
          {pdf.size_bytes ? formatSize(pdf.size_bytes) : ''}
        </span>
      </div>
    </button>
  );
}

// ── Audio row ───────────────────────────────────────────────────

function AudioRow({ audio, isPlaying, onPlay, onPause }) {
  const audioRef = useRef(null);
  const barRef = useRef(null);
  const [progress, setProgress] = useState(0);
  const [displayDuration, setDisplayDuration] = useState(
    audio.duration_seconds ? formatDuration(audio.duration_seconds) : ''
  );

  // Sync play/pause with lifted state
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    if (isPlaying) {
      el.play().catch(() => {});
    } else {
      el.pause();
    }
  }, [isPlaying]);

  const handleTimeUpdate = useCallback(() => {
    const el = audioRef.current;
    if (!el || !el.duration) return;
    setProgress(el.currentTime / el.duration);
  }, []);

  const handleLoadedMetadata = useCallback(() => {
    const el = audioRef.current;
    if (el && el.duration && isFinite(el.duration)) {
      setDisplayDuration(formatDuration(Math.round(el.duration)));
    }
  }, []);

  const handleEnded = useCallback(() => {
    setProgress(0);
    onPause();
  }, [onPause]);

  const handleBarClick = useCallback((e) => {
    const el = audioRef.current;
    const bar = barRef.current;
    if (!el || !bar || !el.duration) return;
    const rect = bar.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    el.currentTime = ratio * el.duration;
    setProgress(ratio);
    if (!isPlaying) onPlay();
  }, [isPlaying, onPlay]);

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
      >
        {isPlaying ? '❚❚' : '▶'}
      </button>
      <div className="audio-row__body">
        <div className="audio-row__top">
          <span className="asset-row__filename">{audio.label}</span>
          <span className="audio-row__duration">{displayDuration}</span>
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
        src={audio.url}
        preload="metadata"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
      />
    </div>
  );
}

// ── Extras row ──────────────────────────────────────────────────

function ExtrasRow({ extra }) {
  const ext = fileExtension(extra.filename);
  return (
    <a
      className="asset-row asset-row--extra"
      href={extra.url}
      download={extra.filename}
    >
      <span className="asset-icon asset-icon--extra">{ext}</span>
      <div className="asset-row__info">
        <span className="asset-row__filename">{extra.filename}</span>
        <span className="asset-row__meta">{formatSize(extra.size_bytes)}</span>
      </div>
    </a>
  );
}

// ── Main component ──────────────────────────────────────────────

export default function AssetRail({
  classData,
  activePdfUrl,
  onPdfSelect,
  playingAudioUrl,
  onAudioPlay,
  onAudioPause,
}) {
  if (!classData) return <div className="placeholder">Lesson files</div>;

  const { pdfs, audio, extras } = classData.class;
  const hasDocs = pdfs.length > 0;
  const hasAudio = audio.length > 0;
  const hasExtras = extras.length > 0;

  if (!hasDocs && !hasAudio && !hasExtras) {
    return (
      <>
        <div className="section-label" style={{ marginBottom: 8 }}>LESSON FILES</div>
        <div className="placeholder">No files for this lesson</div>
      </>
    );
  }

  return (
    <>
      <div className="section-label" style={{ marginBottom: 8 }}>LESSON FILES</div>

      {hasDocs && (
        <div className="asset-section">
          <div className="asset-section__label">DOCUMENTS</div>
          {pdfs.map(pdf => (
            <DocumentRow key={pdf.url} pdf={pdf} onPdfSelect={onPdfSelect} />
          ))}
        </div>
      )}

      {hasAudio && (
        <div className="asset-section">
          <div className="asset-section__label">AUDIO</div>
          {audio.map(a => (
            <AudioRow
              key={a.url}
              audio={a}
              isPlaying={playingAudioUrl === a.url}
              onPlay={() => onAudioPlay(a.url)}
              onPause={onAudioPause}
            />
          ))}
        </div>
      )}

      {hasExtras && (
        <div className="asset-section">
          <div className="asset-section__label">EXTRAS</div>
          {extras.map(e => (
            <ExtrasRow key={e.url} extra={e} />
          ))}
        </div>
      )}
    </>
  );
}
