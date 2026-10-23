import { useState } from 'react';
import { Link, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { Spinner, ErrorMessage, SuccessMessage } from '../../components/UI';
import '../pages.css';

export default function LoginPage() {
  const { login, user } = useAuth();
  const navigate        = useNavigate();
  const location        = useLocation();
  const registered      = location.state?.registered;

  const [form,    setForm]    = useState({ username: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  // Already logged in → declarative redirect
  if (user) {
    return <Navigate to="/" replace />;
  }

  function handleChange(e) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(form);
      navigate('/', { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Login failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-card__logo">
          <span className="auth-card__logo-icon">🎂</span>
          <span className="auth-card__logo-name">BakeCart</span>
        </div>

        <h1 className="auth-card__title">Welcome back</h1>
        <p className="auth-card__subtitle">Sign in to your account to continue shopping</p>

        {registered && !error && (
          <SuccessMessage message="Account created successfully! Please sign in with your credentials." />
        )}

        {error && <ErrorMessage message={error} />}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="login-username">Username</label>
            <input
              id="login-username"
              name="username"
              type="text"
              className="form-input"
              value={form.username}
              onChange={handleChange}
              autoComplete="username"
              required
              aria-required="true"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="login-password">Password</label>
            <input
              id="login-password"
              name="password"
              type="password"
              className="form-input"
              value={form.password}
              onChange={handleChange}
              autoComplete="current-password"
              required
              aria-required="true"
              disabled={loading}
            />
          </div>

          <button
            id="login-submit-btn"
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={loading}
            style={{ width: '100%', marginTop: 'var(--sp-2)' }}
          >
            {loading ? <><Spinner size={18} /> Signing in…</> : 'Sign in'}
          </button>
        </form>

        <div style={{ marginTop: 'var(--sp-4)', padding: 'var(--sp-3)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)', border: '1px solid var(--clr-border)', fontSize: 'var(--text-xs)' }}>
          <p style={{ fontWeight: 600, marginBottom: 'var(--sp-2)', color: 'var(--clr-text-muted)' }}>Demo Accounts (1-Click Fill):</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-1)' }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ justifyContent: 'space-between', padding: '6px 10px', fontSize: '11px', textAlign: 'left' }}
              onClick={() => setForm({ username: 'baker_bob', password: 'baker123' })}
            >
              <span>📦 <strong>Dealer (Supplier):</strong> baker_bob</span>
              <span style={{ color: 'var(--clr-primary)', fontWeight: 600 }}>Fill</span>
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ justifyContent: 'space-between', padding: '6px 10px', fontSize: '11px', textAlign: 'left' }}
              onClick={() => setForm({ username: 'alice', password: 'alice123' })}
            >
              <span>🥖 <strong>Bakery Owner (Buyer):</strong> alice</span>
              <span style={{ color: 'var(--clr-primary)', fontWeight: 600 }}>Fill</span>
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ justifyContent: 'space-between', padding: '6px 10px', fontSize: '11px', textAlign: 'left' }}
              onClick={() => setForm({ username: 'admin', password: 'admin123' })}
            >
              <span>🛡️ <strong>Admin:</strong> admin</span>
              <span style={{ color: 'var(--clr-primary)', fontWeight: 600 }}>Fill</span>
            </button>
          </div>
        </div>

        <div className="auth-footer">
          Don&apos;t have an account?{' '}
          <Link to="/register" id="login-register-link">Create one</Link>
        </div>
      </div>
    </div>
  );
}
