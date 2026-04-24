import { useEffect } from 'react';

export default function LessonHeader({ classData, viewMode, onViewChange }) {
  const cls = classData?.class;
  const mod = classData?.module;

  // Update page title
  useEffect(() => {
    if (cls && mod) {
      document.title = `${mod.number}.${cls.number} ${cls.title} — MediaStudyShelf`;
    } else {
      document.title = 'MediaStudyShelf';
    }
  }, [cls?.title, mod?.number, cls?.number]);

  if (!classData) return null;

  return (
    <div className="lesson-header">
      <div className="lesson-header__left">
        <div className="lesson-header__breadcrumb">
          Module {mod.number} · {mod.title}
        </div>
        <div className="lesson-header__title">
          {mod.number}.{cls.number} {cls.title}
        </div>
      </div>
      <div className="view-toggle">
        {['split', 'video', 'pdf'].map(mode => (
          <button
            key={mode}
            className={`view-toggle__btn${viewMode === mode ? ' view-toggle__btn--active' : ''}`}
            onClick={() => onViewChange(mode)}
          >
            {mode.charAt(0).toUpperCase() + mode.slice(1)}
          </button>
        ))}
      </div>
    </div>
  );
}
