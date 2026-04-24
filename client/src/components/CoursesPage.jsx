import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchTree } from '../lib/api';

export default function CoursesPage() {
  const navigate = useNavigate();
  const [tree, setTree] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchTree()
      .then(data => { setTree(data); setError(null); })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSelect = (course) => {
    const mod = course.modules.find(m => m.classes.length > 0);
    if (mod) {
      navigate(`/course/${course.slug}/${mod.slug}/${mod.classes[0].slug}`);
    }
  };

  return (
    <div className="courses-page">
      <div className="courses-page__header">
        <div className="section-label">COURSES</div>
        <h1 className="courses-page__title">Select a course</h1>
      </div>

      {loading && (
        <div className="courses-grid">
          {[1, 2, 3].map(i => (
            <div key={i} className="course-card course-card--loading">
              <div className="loading-pulse" style={{ width: '70%', height: 14 }} />
              <div className="loading-pulse" style={{ width: '40%', height: 10, marginTop: 8 }} />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="error-state">
          <div className="error-state__title">Could not load courses</div>
          <div className="error-state__message">{error}</div>
        </div>
      )}

      {tree && tree.courses.length === 0 && (
        <div className="empty-state">
          <div className="empty-state__title">No courses found</div>
          <div className="empty-state__message">
            Drop folders into your content directory to get started.
          </div>
        </div>
      )}

      {tree && tree.courses.length > 0 && (
        <div className="courses-grid">
          {tree.courses.map(course => {
            const moduleCount = course.modules.length;
            const classCount = course.modules.reduce((sum, m) => sum + m.classes.length, 0);
            return (
              <button
                key={course.slug}
                className="course-card"
                onClick={() => handleSelect(course)}
              >
                <div className="course-card__title">{course.title}</div>
                <div className="course-card__meta">
                  {moduleCount} {moduleCount === 1 ? 'module' : 'modules'} · {classCount} {classCount === 1 ? 'class' : 'classes'}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
