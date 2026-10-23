import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getB2BBakeries, authorizeB2BBakery } from '../../api/client';
import { PageLoader, ErrorMessage, EmptyState } from '../../components/UI';
import { useAuth } from '../../context/AuthContext';
import './Bakeries.css';

export default function BakeriesPage() {
  const { user } = useAuth();
  const [bakeries, setBakeries] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [authLoadingId, setAuthLoadingId] = useState(null);

  useEffect(() => {
    loadBakeries();
  }, []);

  async function loadBakeries() {
    setLoading(true);
    setError(null);
    try {
      const res = await getB2BBakeries();
      setBakeries(res.bakeries || []);
    } catch (err) {
      setError(err.message || 'Could not load bakeries.');
    } finally {
      setLoading(false);
    }
  }

  async function handleConnect(bakeryId) {
    if (!user) {
      window.location.href = '/login';
      return;
    }
    setAuthLoadingId(bakeryId);
    try {
      await authorizeB2BBakery(bakeryId);
      await loadBakeries();
    } catch (err) {
      alert(err.message || 'Failed to request authorization.');
    } finally {
      setAuthLoadingId(null);
    }
  }

  const filtered = bakeries.filter(b =>
    b.name.toLowerCase().includes(search.toLowerCase()) ||
    (b.address && b.address.toLowerCase().includes(search.toLowerCase())) ||
    (b.description && b.description.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="container" style={{ padding: 'var(--sp-8) 0' }}>
      <div style={{ marginBottom: 'var(--sp-6)' }}>
        <span className="b2b-badge b2b-badge--primary" style={{ marginBottom: 'var(--sp-2)' }}>
          Wholesale Dealer Network
        </span>
        <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 800, margin: 'var(--sp-1) 0' }}>
          Authorized Dealers & Suppliers
        </h1>
        <p style={{ color: 'var(--text-muted)', maxWidth: '640px' }}>
          Connect with trusted wholesale dealers and suppliers, access verified product catalogues, and submit bulk purchase orders for your bakery.
        </p>
      </div>

      <div style={{ marginBottom: 'var(--sp-6)', maxWidth: '400px' }}>
        <input
          type="text"
          className="form-control"
          placeholder="Search dealers by company name or location..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {loading && <PageLoader />}
      {error && <ErrorMessage message={error} onRetry={loadBakeries} />}

      {!loading && !error && filtered.length === 0 && (
        <EmptyState
          icon="📦"
          title="No Dealers Found"
          message="There are currently no active wholesale dealers matching your search."
        />
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="bakery-grid">
          {filtered.map(bakery => (
            <div key={bakery.id} className="bakery-card">
              <div className="bakery-card__header">
                <div>
                  <h2 className="bakery-card__title">{bakery.name}</h2>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                    Owner: {bakery.owner_username}
                  </span>
                </div>
                {bakery.is_authorized ? (
                  <span className="b2b-badge b2b-badge--success">Authorized</span>
                ) : (
                  <span className="b2b-badge b2b-badge--warning">Access Required</span>
                )}
              </div>

              <p className="bakery-card__desc">
                {bakery.description || 'Artisan commercial wholesale bakery supplier.'}
              </p>

              <div className="bakery-card__meta">
                {bakery.address && (
                  <div className="bakery-card__meta-item">
                    <span>📍</span> <span>{bakery.address}</span>
                  </div>
                )}
                {bakery.phone && (
                  <div className="bakery-card__meta-item">
                    <span>📞</span> <span>{bakery.phone}</span>
                  </div>
                )}
                <div className="bakery-card__meta-item">
                  <span>📦</span> <span><strong>{bakery.products_count}</strong> wholesale product lines</span>
                </div>
              </div>

              <div style={{ marginTop: 'auto', display: 'flex', gap: 'var(--sp-2)' }}>
                <Link
                  to={`/bakeries/${bakery.id}`}
                  className="btn btn-primary btn-sm"
                  style={{ flex: 1, textAlign: 'center' }}
                >
                  View Catalogue & Order →
                </Link>
                {!bakery.is_authorized && (
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={authLoadingId === bakery.id}
                    onClick={() => handleConnect(bakery.id)}
                  >
                    {authLoadingId === bakery.id ? 'Connecting...' : 'Connect'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
