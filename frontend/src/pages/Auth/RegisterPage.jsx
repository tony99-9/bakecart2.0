import { useState } from 'react';
import { Link, useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { register } from '../../api/client';
import { ApiError } from '../../api/client';
import { Spinner, ErrorMessage, FieldErrors } from '../../components/UI';
import '../pages.css';

const INITIAL = {
  first_name: '',
  last_name: '',
  username: '',
  email: '',
  password: '',
  password_confirm: '',
  role: 'dealer',
  business_name: '',
};

export default function RegisterPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [form,     setForm]     = useState(INITIAL);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [details,  setDetails]  = useState(null); // field-level validation errors

  if (user) {
    return <Navigate to="/" replace />;
  }

  function handleChange(e) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  function handleRoleSelect(role) {
    setForm(f => ({ ...f, role }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setDetails(null);
    try {
      await register(form);
      // Registration succeeds but does NOT auto-log in (per backend design).
      // Redirect to login with a success hint.
      navigate('/login', { state: { registered: true }, replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        setDetails(err.details);
      } else {
        setError('Registration failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  const isSeller = form.role === 'seller';

  const fields = [
    { id: 'reg-first-name',    name: 'first_name',       label: 'First name',        type: 'text',     autocomplete: 'given-name' },
    { id: 'reg-last-name',     name: 'last_name',        label: 'Last name',         type: 'text',     autocomplete: 'family-name' },
    { id: 'reg-username',      name: 'username',         label: 'Username',          type: 'text',     autocomplete: 'username' },
    { id: 'reg-email',         name: 'email',            label: 'Email (optional)',  type: 'email',    autocomplete: 'email',    required: false },
    { id: 'reg-business-name', name: 'business_name',    label: isSeller ? 'Dealership / Company Name' : 'Bakery Name', type: 'text', required: true },
    { id: 'reg-password',      name: 'password',         label: 'Password',          type: 'password', autocomplete: 'new-password' },
    { id: 'reg-confirm',       name: 'password_confirm', label: 'Confirm password',  type: 'password', autocomplete: 'new-password' },
  ];

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-card__logo">
          <span className="auth-card__logo-icon">🥖</span>
          <span className="auth-card__logo-name">BakeCart B2B</span>
        </div>

        <h1 className="auth-card__title">Create B2B Account</h1>
        <p className="auth-card__subtitle">Join the digital bakery wholesale marketplace</p>

        {error && <ErrorMessage message={error} />}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {/* Role selector */}
          <div className="form-group">
            <label className="form-label">I want to register as:</label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)' }}>
              <button
                type="button"
                id="role-select-seller"
                onClick={() => handleRoleSelect('seller')}
                style={{
                  padding: 'var(--sp-3)',
                  borderRadius: 'var(--radius-md)',
                  border: `2px solid ${form.role === 'seller' ? 'var(--clr-primary)' : 'var(--clr-border)'}`,
                  background: form.role === 'seller' ? 'var(--clr-surface-2)' : 'transparent',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}
              >
                <span style={{ fontSize: '1.25rem' }}>📦</span>
                <strong style={{ fontSize: 'var(--text-sm)', color: form.role === 'seller' ? 'var(--clr-primary)' : 'var(--clr-text)' }}>
                  Dealer (Supplier)
                </strong>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-muted)', lineHeight: 1.2 }}>
                  Sell products & supplies to bakeries
                </span>
              </button>

              <button
                type="button"
                id="role-select-dealer"
                onClick={() => handleRoleSelect('dealer')}
                style={{
                  padding: 'var(--sp-3)',
                  borderRadius: 'var(--radius-md)',
                  border: `2px solid ${form.role === 'dealer' ? 'var(--clr-primary)' : 'var(--clr-border)'}`,
                  background: form.role === 'dealer' ? 'var(--clr-surface-2)' : 'transparent',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}
              >
                <span style={{ fontSize: '1.25rem' }}>🥖</span>
                <strong style={{ fontSize: 'var(--text-sm)', color: form.role === 'dealer' ? 'var(--clr-primary)' : 'var(--clr-text)' }}>
                  Bakery Owner (Buyer)
                </strong>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-muted)', lineHeight: 1.2 }}>
                  Order products for your bakery
                </span>
              </button>
            </div>
          </div>

          {fields.map(f => (
            <div className="form-group" key={f.name}>
              <label className="form-label" htmlFor={f.id}>{f.label}</label>
              <input
                id={f.id}
                name={f.name}
                type={f.type}
                className="form-input"
                value={form[f.name]}
                onChange={handleChange}
                autoComplete={f.autocomplete}
                required={f.required !== false}
                aria-required={f.required !== false ? 'true' : 'false'}
                disabled={loading}
                aria-describedby={details?.[f.name] ? `${f.id}-error` : undefined}
                placeholder={f.name === 'business_name' ? (isSeller ? "e.g. Apex Wholesale Bakery Supplies" : "e.g. Bob's Artisan Sourdough Bakery") : undefined}
              />
              {details?.[f.name] && (
                <span id={`${f.id}-error`}>
                  <FieldErrors errors={details[f.name]} />
                </span>
              )}
            </div>
          ))}

          <button
            id="register-submit-btn"
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={loading}
            style={{ width: '100%', marginTop: 'var(--sp-2)' }}
          >
            {loading ? <><Spinner size={18} /> Creating account…</> : `Register as ${isSeller ? 'Dealer (Supplier)' : 'Bakery Owner'}`}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account?{' '}
          <Link to="/login" id="register-login-link">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
