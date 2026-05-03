import AudioStreamPlayer from './AudioStreamPlayer';

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
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
            <AudioStreamPlayer
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
