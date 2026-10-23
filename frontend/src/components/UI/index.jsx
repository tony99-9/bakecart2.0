/**
 * Shared UI primitives for BakeCart 2.0.
 * Spinner, ErrorMessage, EmptyState, PageLoader, ConfirmDialog.
 * Plain CSS via index.css tokens.
 */

/* ── Spinner ──────────────────────────────────────────────── */
export function Spinner({ size = 24, label = 'Loading…' }) {
  return (
    <span
      role="status"
      aria-label={label}
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        borderRadius: '50%',
        border: `3px solid var(--clr-border)`,
        borderTopColor: 'var(--clr-primary)',
        animation: 'spin .7s linear infinite',
        flexShrink: 0,
      }}
    />
  );
}

/* ── Full-page loader ─────────────────────────────────────── */
export function PageLoader({ label = 'Loading…' }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        gap: 'var(--sp-4)',
        color: 'var(--clr-text-muted)',
      }}
    >
      <Spinner size={40} label={label} />
      <p style={{ fontSize: 'var(--text-sm)' }}>{label}</p>
    </div>
  );
}

/* ── Error message ────────────────────────────────────────── */
export function ErrorMessage({ message, onRetry }) {
  return (
    <div className="alert alert--error animate-fade-in" role="alert">
      <span aria-hidden="true" style={{ flexShrink: 0 }}>⚠️</span>
      <div style={{ flex: 1 }}>
        <p>{message}</p>
        {onRetry && (
          <button
            className="btn btn-sm"
            onClick={onRetry}
            style={{ marginTop: 'var(--sp-2)', color: 'var(--clr-error)', border: '1px solid var(--clr-error)', borderRadius: 'var(--radius-full)', padding: '4px 12px', fontSize: 'var(--text-xs)', cursor: 'pointer', background: 'transparent' }}
          >
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Field-level validation error list ───────────────────── */
export function FieldErrors({ errors }) {
  if (!errors) return null;
  const messages = Array.isArray(errors) ? errors : [errors];
  return (
    <ul role="list" style={{ paddingLeft: 0, listStyle: 'none' }}>
      {messages.map((m, i) => (
        <li key={i} className="form-error">{m}</li>
      ))}
    </ul>
  );
}

/* ── Empty state ──────────────────────────────────────────── */
export function EmptyState({ icon = '🥐', title, description, action }) {
  return (
    <div
      className="animate-fade-in"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: 'var(--sp-16) var(--sp-8)',
        gap: 'var(--sp-4)',
      }}
    >
      <span style={{ fontSize: '3rem', lineHeight: 1 }}>{icon}</span>
      <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'var(--text-xl)', color: 'var(--clr-text)' }}>
        {title}
      </h2>
      {description && (
        <p style={{ color: 'var(--clr-text-muted)', maxWidth: 360, fontSize: 'var(--text-sm)' }}>
          {description}
        </p>
      )}
      {action}
    </div>
  );
}

/* ── Skeleton card ────────────────────────────────────────── */
export function SkeletonCard() {
  return (
    <div className="card" aria-hidden="true" style={{ padding: 'var(--sp-4)' }}>
      <div className="skeleton" style={{ height: 200, borderRadius: 'var(--radius-md)', marginBottom: 'var(--sp-3)' }} />
      <div className="skeleton" style={{ height: 18, width: '70%', marginBottom: 'var(--sp-2)' }} />
      <div className="skeleton" style={{ height: 14, width: '45%', marginBottom: 'var(--sp-4)' }} />
      <div className="skeleton" style={{ height: 36, borderRadius: 'var(--radius-full)' }} />
    </div>
  );
}

/* ── Inline success / confirm message ────────────────────── */
export function SuccessMessage({ message }) {
  return (
    <div className="alert alert--success animate-fade-in" role="status">
      <span aria-hidden="true">✅</span>
      <p>{message}</p>
    </div>
  );
}
