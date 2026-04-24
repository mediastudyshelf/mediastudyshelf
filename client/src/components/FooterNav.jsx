import { Link } from 'react-router-dom';

export default function FooterNav({ nav }) {
  if (!nav) return null;

  const { prev, next } = nav;
  if (!prev && !next) return null;

  return (
    <div className="footer-nav">
      <div className="footer-nav__slot">
        {prev && (
          <Link
            className="footer-nav__link"
            to={`/course/${prev.course}/${prev.module}/${prev.class}`}
          >
            ← {prev.title}
          </Link>
        )}
      </div>
      <div className="footer-nav__slot footer-nav__slot--right">
        {next && (
          <Link
            className="footer-nav__link"
            to={`/course/${next.course}/${next.module}/${next.class}`}
          >
            {next.title} →
          </Link>
        )}
      </div>
    </div>
  );
}
