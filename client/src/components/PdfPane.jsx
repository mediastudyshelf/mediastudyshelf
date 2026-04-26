import { useEffect, useRef, useState, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;

const ZOOM_STEPS = [50, 75, 100, 125, 150, 200];

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

export default function PdfPane({ pdfs, activePdfUrl, onPdfSelect, expanded, hidden }) {
  const activePdf = pdfs?.find(p => p.url === activePdfUrl) || pdfs?.[0];

  const canvasRef = useRef(null);
  const viewerRef = useRef(null);
  const pdfDocRef = useRef(null);
  const renderTaskRef = useRef(null);
  const loadingUrlRef = useRef(null);
  const menuRef = useRef(null);

  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [docRevision, setDocRevision] = useState(0);
  const [zoom, setZoom] = useState(100);
  const [menuOpen, setMenuOpen] = useState(false);

  // Load PDF document when active PDF changes
  useEffect(() => {
    if (!activePdf) {
      if (pdfDocRef.current) {
        pdfDocRef.current.destroy();
        pdfDocRef.current = null;
      }
      setTotalPages(0);
      setCurrentPage(1);
      return;
    }

    const url = activePdf.url;
    loadingUrlRef.current = url;
    let cancelled = false;

    if (renderTaskRef.current) {
      renderTaskRef.current.cancel();
      renderTaskRef.current = null;
    }

    // Destroy previous document before loading new one
    if (pdfDocRef.current) {
      pdfDocRef.current.destroy();
      pdfDocRef.current = null;
    }

    const loadTask = pdfjsLib.getDocument(url);
    loadTask.promise.then(doc => {
      if (cancelled || loadingUrlRef.current !== url) {
        doc.destroy();
        return;
      }
      pdfDocRef.current = doc;
      setTotalPages(doc.numPages);
      setCurrentPage(1);
      setDocRevision(r => r + 1);
    }).catch(err => {
      if (err.name !== 'RenderingCancelledException' && !cancelled) {
        console.error('PDF load failed:', err);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [activePdf?.url]);

  // Render the current page (re-renders when PDF document or page changes)
  useEffect(() => {
    const doc = pdfDocRef.current;
    const canvas = canvasRef.current;
    if (!doc || !canvas || totalPages === 0) return;

    if (renderTaskRef.current) {
      renderTaskRef.current.cancel();
      renderTaskRef.current = null;
    }

    if (viewerRef.current) viewerRef.current.scrollTop = 0;

    doc.getPage(currentPage).then(page => {
      const scale = zoom / 100;
      const viewport = page.getViewport({ scale });
      const ctx = canvas.getContext('2d');

      canvas.width = viewport.width;
      canvas.height = viewport.height;

      const task = page.render({ canvasContext: ctx, viewport });
      renderTaskRef.current = task;

      task.promise.then(() => {
        renderTaskRef.current = null;
      }).catch(err => {
        if (err.name !== 'RenderingCancelledException') {
          console.error('PDF render failed:', err);
        }
      });
    });
  }, [currentPage, zoom, totalPages, docRevision]);

  // Keyboard: page nav + Escape to close menu
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape' && menuOpen) {
      setMenuOpen(false);
      return;
    }
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      setCurrentPage(p => Math.min(p + 1, totalPages));
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      setCurrentPage(p => Math.max(p - 1, 1));
    }
  }, [totalPages, menuOpen]);

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

  const zoomIn = () => {
    const next = ZOOM_STEPS.find(s => s > zoom);
    if (next) setZoom(next);
  };

  const zoomOut = () => {
    const prev = [...ZOOM_STEPS].reverse().find(s => s < zoom);
    if (prev) setZoom(prev);
  };

  const handleSelectPdf = (pdf) => {
    onPdfSelect(pdf.url);
    setMenuOpen(false);
  };

  const paneClass = [
    'pdf-pane',
    expanded && 'pdf-pane--expanded',
    hidden && 'pdf-pane--hidden',
  ].filter(Boolean).join(' ');

  // No PDFs
  if (!pdfs || pdfs.length === 0) {
    return (
      <div className={paneClass}>
        <div className="pdf-pane__empty">No PDFs for this lesson</div>
      </div>
    );
  }

  const hasMultiple = pdfs.length > 1;
  const activeIndex = pdfs.findIndex(p => p.url === activePdfUrl) + 1;

  return (
    <div
      className={paneClass}
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      <div className="pdf-header">
        <div className="pdf-selector-wrap" ref={menuRef}>
          <button
            className={`pdf-selector${hasMultiple ? ' pdf-selector--clickable' : ''}`}
            onClick={() => hasMultiple && setMenuOpen(o => !o)}
            disabled={!hasMultiple}
          >
            <span className="pdf-selector__icon">PDF</span>
            <span className="pdf-selector__filename">{activePdf?.filename}</span>
            {hasMultiple && (
              <>
                <span className="pdf-selector__counter">{activeIndex} of {pdfs.length}</span>
                <span className="pdf-selector__chevron">▾</span>
              </>
            )}
          </button>

          {menuOpen && (
            <div className="pdf-menu">
              {pdfs.map(pdf => {
                const isActive = pdf.url === activePdfUrl;
                return (
                  <button
                    key={pdf.url}
                    className={`pdf-menu__item${isActive ? ' pdf-menu__item--active' : ''}`}
                    onClick={() => handleSelectPdf(pdf)}
                  >
                    <span className="pdf-menu__icon">PDF</span>
                    <div className="pdf-menu__info">
                      <span className="pdf-menu__filename">{pdf.filename}</span>
                      <span className="pdf-menu__meta">
                        {pdf.pages != null ? `${pdf.pages} pages` : ''}
                        {pdf.pages != null && pdf.size_bytes ? ' · ' : ''}
                        {pdf.size_bytes ? formatSize(pdf.size_bytes) : ''}
                      </span>
                    </div>
                    {isActive && <span className="pdf-menu__check">✓</span>}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="pdf-controls">
          <div className="pdf-controls__zoom">
            <button className="pdf-controls__btn" onClick={zoomOut} disabled={zoom <= ZOOM_STEPS[0]}>−</button>
            <span className="pdf-controls__zoom-level" onClick={() => setZoom(100)}>{zoom}%</span>
            <button className="pdf-controls__btn" onClick={zoomIn} disabled={zoom >= ZOOM_STEPS[ZOOM_STEPS.length - 1]}>+</button>
          </div>
          <div className="pdf-controls__pages">
            <button
              className="pdf-controls__btn"
              onClick={() => setCurrentPage(p => Math.max(p - 1, 1))}
              disabled={currentPage <= 1}
            >‹</button>
            <span className="pdf-controls__page-num">{currentPage} / {totalPages}</span>
            <button
              className="pdf-controls__btn"
              onClick={() => setCurrentPage(p => Math.min(p + 1, totalPages))}
              disabled={currentPage >= totalPages}
            >›</button>
          </div>
        </div>
      </div>
      <div className="pdf-viewer" ref={viewerRef}>
        <canvas ref={canvasRef} className="pdf-viewer__canvas" />
      </div>
    </div>
  );
}
