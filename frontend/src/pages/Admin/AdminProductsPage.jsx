import { useState, useEffect, useCallback, useRef } from 'react';
import { getAdminProducts, activateAdminProduct, getCategories, ApiError } from '../../api/client';
import { PageLoader, ErrorMessage, Spinner, SuccessMessage } from '../../components/UI';
import AdminLayout from './AdminLayout';

const BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export default function AdminProductsPage() {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [page, setPage] = useState(1);
  const [numPages, setNumPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [activatingId, setActivatingId] = useState(null);
  const [actionSuccess, setActionSuccess] = useState('');
  const [actionError, setActionError] = useState(null);
  const searchTimer = useRef(null);

  const load = useCallback(async (s, c, act, p) => {
    setLoading(true);
    setError(null);
    try {
      const [prodRes, catRes] = await Promise.all([
        getAdminProducts({ search: s, category: c, active: act, page: p }),
        categories.length ? Promise.resolve({ categories }) : getCategories(),
      ]);
      setProducts(prodRes.results ?? []);
      setNumPages(prodRes.num_pages ?? 1);
      if (catRes.categories) setCategories(catRes.categories);
    } catch (err) {
      setError(err.message ?? 'Could not load products.');
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    load(search, category, activeFilter, page);
  }, [search, category, activeFilter, page]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSearchChange(e) {
    const val = e.target.value;
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setSearch(val);
      setPage(1);
    }, 350);
  }

  async function handleActivate(productId) {
    setActivatingId(productId);
    setActionError(null);
    setActionSuccess('');
    try {
      await activateAdminProduct(productId);
      setActionSuccess(`Product #${productId} has been reactivated and is now visible to customers.`);
      setTimeout(() => setActionSuccess(''), 4000);
      await load(search, category, activeFilter, page);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Failed to reactivate product.');
    } finally {
      setActivatingId(null);
    }
  }

  return (
    <AdminLayout>
      <div className="data-table-card">
        {/* Filter Bar */}
        <div className="admin-filter-bar">
          <div className="shop-search" style={{ minWidth: '220px' }}>
            <span aria-hidden="true" style={{ color: 'var(--clr-text-subtle)' }}>🔍</span>
            <input
              type="search"
              placeholder="Search products…"
              onChange={handleSearchChange}
              aria-label="Search all marketplace products"
            />
          </div>

          <div style={{ display: 'flex', gap: 'var(--sp-3)', flexWrap: 'wrap' }}>
            <select
              className="admin-select"
              value={category}
              onChange={e => { setCategory(e.target.value); setPage(1); }}
              aria-label="Filter by category"
            >
              <option value="">All Categories</option>
              {categories.filter(c => c.code !== 'ALL').map(c => (
                <option key={c.code} value={c.code}>{c.label}</option>
              ))}
            </select>

            <select
              className="admin-select"
              value={activeFilter}
              onChange={e => { setActiveFilter(e.target.value); setPage(1); }}
              aria-label="Filter by active status"
            >
              <option value="">All Statuses</option>
              <option value="true">Active Only</option>
              <option value="false">Deactivated Only</option>
            </select>
          </div>
        </div>

        {actionSuccess && <SuccessMessage message={actionSuccess} />}
        {actionError && <ErrorMessage message={actionError} />}
        {error && <ErrorMessage message={error} onRetry={() => load(search, category, activeFilter, page)} />}

        {loading ? (
          <PageLoader />
        ) : products.length === 0 ? (
          <div style={{ padding: 'var(--sp-12)', textAlign: 'center', color: 'var(--clr-text-muted)' }}>
            No products match the selected criteria.
          </div>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Seller</th>
                    <th>Category</th>
                    <th>Price</th>
                    <th>Stock</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map(p => {
                    const imgSrc = p.image
                      ? `${BASE}${p.image.startsWith('/') ? '' : '/'}${p.image}`
                      : null;
                    const isActivating = activatingId === p.id;

                    return (
                      <tr key={p.id}>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
                            {imgSrc ? (
                              <img src={imgSrc} alt="" className="product-row-thumb" />
                            ) : (
                              <div className="product-row-thumb-fallback" aria-hidden="true">🍰</div>
                            )}
                            <div>
                              <strong>{p.title}</strong>
                              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-subtle)', display: 'block' }}>
                                ID: #{p.id}
                              </span>
                            </div>
                          </div>
                        </td>

                        <td>
                          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--clr-text)' }}>
                            {p.seller_username || 'Unknown'}
                          </span>
                        </td>

                        <td>
                          <span className="badge" style={{ background: 'var(--clr-surface-2)' }}>
                            {p.category_label || p.category}
                          </span>
                        </td>

                        <td>€{Number(p.price).toFixed(2)}</td>

                        <td>
                          <span
                            className={`stock-pill ${
                              p.quantity === 0
                                ? 'stock-pill--out'
                                : p.quantity <= 5
                                ? 'stock-pill--low'
                                : 'stock-pill--in'
                            }`}
                          >
                            {p.quantity} units
                          </span>
                        </td>

                        <td>
                          <span className={`badge ${p.is_active ? 'badge-active' : 'badge-inactive'}`}>
                            {p.is_active ? 'Active' : 'Deactivated'}
                          </span>
                        </td>

                        <td style={{ textAlign: 'right' }}>
                          {!p.is_active && (
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              onClick={() => handleActivate(p.id)}
                              disabled={isActivating}
                            >
                              {isActivating ? <Spinner size={12} /> : 'Reactivate Product'}
                            </button>
                          )}
                          {p.is_active && (
                            <span style={{ fontSize: 'var(--text-xs)', color: '#2e7d32' }}>
                              ✓ Live
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {numPages > 1 && (
              <div style={{ padding: 'var(--sp-4)', display: 'flex', justifyContent: 'center' }}>
                <nav className="shop-pagination" aria-label="Admin products pagination">
                  <button
                    className="page-btn"
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page <= 1}
                  >
                    ←
                  </button>
                  {Array.from({ length: numPages }, (_, i) => i + 1)
                    .filter(p => Math.abs(p - page) <= 2)
                    .map(p => (
                      <button
                        key={p}
                        className={`page-btn ${p === page ? 'page-btn--active' : ''}`}
                        onClick={() => setPage(p)}
                      >
                        {p}
                      </button>
                    ))}
                  <button
                    className="page-btn"
                    onClick={() => setPage(p => Math.min(numPages, p + 1))}
                    disabled={page >= numPages}
                  >
                    →
                  </button>
                </nav>
              </div>
            )}
          </>
        )}
      </div>
    </AdminLayout>
  );
}
