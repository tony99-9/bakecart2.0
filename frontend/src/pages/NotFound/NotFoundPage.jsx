import { Link } from 'react-router-dom';

/** 404 Not Found — used as the catch-all route */
export default function NotFoundPage() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '80vh',
        textAlign: 'center',
        padding: 'var(--sp-8)',
        gap: 'var(--sp-4)',
      }}
    >
      <span style={{ fontSize: '4rem' }}>🎂</span>
      <h1
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--text-4xl)',
          color: 'var(--clr-primary)',
        }}
      >
        404
      </h1>
      <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'var(--text-2xl)', color: 'var(--clr-text)' }}>
        Page not found
      </h2>
      <p style={{ color: 'var(--clr-text-muted)', maxWidth: 360, fontSize: 'var(--text-sm)' }}>
        Looks like this page got eaten. Let&apos;s get you back to the bakery.
      </p>
      <Link to="/" className="btn btn-primary btn-lg" id="404-home-btn">
        Back to home
      </Link>
    </div>
  );
}
