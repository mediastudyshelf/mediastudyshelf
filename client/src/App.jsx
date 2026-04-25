import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchTree, fetchClass } from './lib/api';
import CourseNav from './components/CourseNav';
import LessonHeader from './components/LessonHeader';
import VideoPane from './components/VideoPane';
import SplitDivider from './components/SplitDivider';
import PdfPane from './components/PdfPane';
import FooterNav from './components/FooterNav';
import AssetRail from './components/AssetRail';

export default function App() {
  const { courseSlug, moduleSlug, classSlug } = useParams();
  const navigate = useNavigate();

  const [tree, setTree] = useState(null);
  const [treeLoading, setTreeLoading] = useState(true);
  const [treeError, setTreeError] = useState(null);

  const [classData, setClassData] = useState(null);
  const [classLoading, setClassLoading] = useState(false);
  const [classError, setClassError] = useState(null);

  const [viewMode, setViewMode] = useState('split');
  const [activeVideoUrl, setActiveVideoUrl] = useState(null);
  const [activePdfUrl, setActivePdfUrl] = useState(null);
  const [playingAudioUrl, setPlayingAudioUrl] = useState(null);

  // Fetch tree on mount
  useEffect(() => {
    setTreeLoading(true);
    fetchTree()
      .then(data => {
        setTree(data);
        setTreeError(null);
      })
      .catch(err => setTreeError(err.message))
      .finally(() => setTreeLoading(false));
  }, []);

  // Redirect to courses page if no course selected
  useEffect(() => {
    if (tree && !courseSlug) {
      navigate('/courses', { replace: true });
    }
  }, [tree, courseSlug, navigate]);

  // Fetch class data when slugs change — keep previous class visible during load
  useEffect(() => {
    if (!courseSlug || !moduleSlug || !classSlug) return;

    setClassLoading(true);
    setClassError(null);
    setPlayingAudioUrl(null);

    fetchClass(courseSlug, moduleSlug, classSlug)
      .then(data => {
        setClassData(data);
        setClassError(null);
        const primaryVideo = data.class.videos.find(v => v.is_primary);
        setActiveVideoUrl(primaryVideo?.url || data.class.videos[0]?.url || null);
        const primary = data.class.pdfs.find(p => p.is_primary);
        setActivePdfUrl(primary?.url || data.class.pdfs[0]?.url || null);
        if (!data.class.videos.length) {
          setViewMode('pdf');
        } else if (!data.class.pdfs.length) {
          setViewMode('video');
        } else {
          setViewMode('split');
        }
      })
      .catch(err => {
        setClassData(null);
        setActivePdfUrl(null);
        setClassError(err.message);
      })
      .finally(() => setClassLoading(false));
  }, [courseSlug, moduleSlug, classSlug]);

  // ── Tree-level error: backend unreachable or broken ──────────
  if (treeError) {
    return (
      <div className="app-layout">
        <div className="left-rail" />
        <main className="main-area">
          <div className="error-state">
            <div className="error-state__title">Could not load courses</div>
            <div className="error-state__message">{treeError}</div>
          </div>
        </main>
        <div className="right-rail" />
      </div>
    );
  }

  // ── Empty content folder ─────────────────────────────────────
  if (!treeLoading && tree && tree.courses.length === 0) {
    return (
      <div className="app-layout">
        <nav className="left-rail">
          <div className="section-label">COURSE</div>
        </nav>
        <main className="main-area">
          <div className="empty-state">
            <div className="empty-state__title">No courses found</div>
            <div className="empty-state__message">
              Drop folders into your content directory to get started.
              <br /><br />
              Expected structure:<br />
              <code>/content/01-course-name/01-module/01-class/</code>
            </div>
          </div>
        </main>
        <div className="right-rail" />
      </div>
    );
  }

  // ── Class-level error (404 or network) ───────────────────────
  const mainContent = classError ? (
    <div className="error-state">
      <div className="error-state__title">{classError}</div>
      {tree && tree.courses[0] && (
        <a
          className="error-state__link"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            const c = tree.courses[0];
            const m = c.modules[0];
            const cl = m.classes[0];
            navigate(`/course/${c.slug}/${m.slug}/${cl.slug}`);
          }}
        >
          Go to first lesson
        </a>
      )}
    </div>
  ) : null;

  const [videoHeight, setVideoHeight] = useState(240);
  const contentRef = useRef(null);

  const handleDividerDrag = useCallback((clientY) => {
    const el = contentRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const newHeight = Math.max(100, Math.min(clientY - rect.top, rect.height - 100));
    setVideoHeight(newHeight);
  }, []);

  const videos = classData?.class?.videos || [];
  const pdfs = classData?.class?.pdfs || [];
  const showVideo = viewMode !== 'pdf';
  const showPdf = viewMode !== 'video';
  const isSplit = showVideo && showPdf;

  return (
    <div className="app-layout">
      <nav className="left-rail">
        <CourseNav
          tree={tree}
          loading={treeLoading}
          courseSlug={courseSlug}
          moduleSlug={moduleSlug}
          classSlug={classSlug}
        />
      </nav>

      <main className="main-area">
        <LessonHeader
          classData={classData}
          viewMode={viewMode}
          onViewChange={setViewMode}
        />
        {mainContent || (
          <>
            <div className="main-content" ref={contentRef}>
              <VideoPane
                videos={videos}
                activeVideoUrl={activeVideoUrl}
                onVideoSelect={setActiveVideoUrl}
                expanded={viewMode === 'video'}
                hidden={!showVideo}
                height={isSplit ? videoHeight : undefined}
              />
              {isSplit && <SplitDivider onDrag={handleDividerDrag} />}
              {classData && (
                <PdfPane
                  pdfs={pdfs}
                  activePdfUrl={activePdfUrl}
                  onPdfSelect={setActivePdfUrl}
                  expanded={viewMode === 'pdf'}
                  hidden={!showPdf}
                />
              )}
            </div>
            <FooterNav nav={classData?.nav} />
          </>
        )}
      </main>

      <aside className="right-rail">
        <AssetRail
          classData={classData}
          activePdfUrl={activePdfUrl}
          onPdfSelect={setActivePdfUrl}
          playingAudioUrl={playingAudioUrl}
          onAudioPlay={setPlayingAudioUrl}
          onAudioPause={() => setPlayingAudioUrl(null)}
        />
      </aside>
    </div>
  );
}
