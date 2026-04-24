import { Link } from 'react-router-dom';

export default function CourseNav({ tree, loading, courseSlug, moduleSlug, classSlug }) {
  if (loading) {
    return (
      <>
        <div className="section-label">COURSE</div>
        <div className="course-nav__title loading-pulse" style={{ width: '80%', height: 14 }} />
        <div className="loading-pulse" style={{ width: '60%', height: 10, marginTop: 16 }} />
        <div className="loading-pulse" style={{ width: '90%', height: 12, marginTop: 8 }} />
        <div className="loading-pulse" style={{ width: '70%', height: 12, marginTop: 4 }} />
      </>
    );
  }

  if (!tree || tree.courses.length === 0) {
    return null;
  }

  const course = tree.courses.find(c => c.slug === courseSlug) || tree.courses[0];

  return (
    <>
      <div className="section-label">COURSE</div>
      <div className="course-nav__title">{course.title}</div>
      {course.modules.map((mod, mi) => (
        <div key={mod.slug}>
          <div className="module-header">
            Module {mi + 1} · {mod.title}
          </div>
          {mod.classes.map(cls => {
            const isActive = cls.slug === classSlug && mod.slug === moduleSlug;
            const className = `class-row${isActive ? ' class-row--active' : ''}`;
            return (
              <Link
                key={cls.slug}
                to={`/course/${course.slug}/${mod.slug}/${cls.slug}`}
                className={className}
              >
                <span className="class-row__circle" />
                {cls.title}
              </Link>
            );
          })}
        </div>
      ))}
    </>
  );
}
