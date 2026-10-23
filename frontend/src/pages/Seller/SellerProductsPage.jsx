import { useState, useEffect, useCallback, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getSellerProducts, deleteSellerProduct, ApiError } from '../../api/client';
import { PageLoader, ErrorMessage, EmptyState, Spinner } from '../../components/UI';
import SellerLayout from './SellerLayout';

const BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export default function SellerProductsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSearch = searchParams.get('search') ?? '';
  const initialPage = Number(searchParams.get('page') ?? 1);

  const [search, setSearch] = useState(initialSearch);
  const [page, setPage] = useState(initialPage);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [deactivatingId, setDeactivatingId] = useState(null);
  const [actionError, setActionError] = useState(null);
  const searchTimer = useRef(null);

  const load = useCallback(async (s, p) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getSellerProducts({ search: s, page: p });
      setData(res);
    } catch (err) {
      setError(err.message ?? 'Could not load seller products.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(search, page);
    setSearchParams(
      Object.fromEntries(
        [['search', search], ['page', String(page)]].filter(([, v]) => v && v !== '1')
      )
    );
  }, [search, page]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSearchChange(e) {
    const val = e.target.value;
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setSearch(val);
      setPage(1);
    }, 350);
  }

  async function handleDeactivate(id) {
    if (!window.confirm('Are you sure you want to deactivate this product? It will be hidden from public browsing.')) {
      return;
    }
    setDeactivatingId(id);
    setActionError(null);
    try {
      await deleteSellerProduct(id);
      await load(search, page);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Failed to deactivate product.');
    } finally {
      setDeactivatingId(null);
    }
  }

  return (
    <SellerLayout>
      <div className="data-table-card">
        {/* Toolbar */}
        <div className="data-table-toolbar">
          <div className="shop-search" style={{ minWidth: '260px' }}>
            <span aria-hidden="true" style={{ color: 'var(--clr-text-subtle)' }}>🔍</span>
            <input
              type="search"
              placeholder="Search your products…"
              defaultValue={initialSearch}
              onChange={handleSearchChange}
              aria-label="Search your products"
            />
          </div>

          <Link to="/seller/products/new" className="btn btn-primary btn-sm">
            + New Product
          </Link>
        </div>

        {actionError && <ErrorMessage message={actionError} />}
        {error && <ErrorMessage message={error} onRetry={() => load(search, page)} />}

        {loading ? (
          <PageLoader />
        ) : data?.results?.length === 0 ? (
          <EmptyState
            icon="🍰"
            title="No products listed"
            description={search ? `No products match "${search}".` : 'You have not added any products to your bakery catalogue yet.'}
            action={<Link to="/seller/products/new" className="btn btn-primary">+ Add Your First Product</Link>}
          />
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Category</th>
                    <th>Price</th>
                    <th>Stock</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map(prod => {
                    const imgSrc = prod.image
                      ? `${BASE}${prod.image.startsWith('/') ? '' : '/'}${prod.image}`
                      : null;
                    const isDeactivating = deactivatingId === prod.id;

                    return (
                      <tr key={prod.id}>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
                            {imgSrc ? (
                              <img src={imgSrc} alt="" className="product-row-thumb" />
                            ) : (
                              <div className="product-row-thumb-fallback" aria-hidden="true">🍰</div>
                            )}
                            <div>
                              <strong style={{ display: 'block', color: 'var(--clr-text)' }}>
                                {prod.title}
                              </strong>
                              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-subtle)' }}>
                                ID: #{prod.id}
                              </span>
                            </div>
                          </div>
                        </td>

                        <td>
                          <span className="badge" style={{ background: 'var(--clr-surface-2)' }}>
                            {prod.category_label || prod.category}
                          </span>
                        </td>

                        <td>€{Number(prod.price).toFixed(2)}</td>

                        <td>
                          <span
                            className={`stock-pill ${
                              prod.quantity === 0
                                ? 'stock-pill--out'
                                : prod.quantity <= 5
                                ? 'stock-pill--low'
                                : 'stock-pill--in'
                            }`}
                          >
                            {prod.quantity} units
                          </span>
                        </td>

                        <td>
                          <span
                            className={`badge ${prod.is_active ? 'badge-active' : 'badge-inactive'}`}
                          >
                            {prod.is_active ? 'Active' : 'Deactivated'}
                          </span>
                        </td>

                        <td style={{ textAlign: 'right' }}>
                          <div style={{ display: 'inline-flex', gap: 'var(--sp-2)' }}>
                            <Link
                              to={`/seller/products/${prod.id}/edit`}
                              className="btn btn-secondary btn-sm"
                            >
                              Edit
                            </Link>

                            {prod.is_active && (
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => handleDeactivate(prod.id)}
                                disabled={isDeactivating}
                                style={{ color: '#c62828' }}
                              >
                                {isDeactivating ? <Spinner size={12} /> : 'Deactivate'}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {data.num_pages > 1 && (
              <div style={{ padding: 'var(--sp-4)', display: 'flex', justifyContent: 'center' }}>
                <nav className="shop-pagination" aria-label="Inventory pagination">
                  <button
                    className="page-btn"
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page <= 1}
                  >
                    ←
                  </button>
                  {Array.from({ length: data.num_pages }, (_, i) => i + 1)
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
                    onClick={() => setPage(p => Math.min(data.num_pages, p + 1))}
                    disabled={page >= data.num_pages}
                  >
                    →
                  </button>
                </nav>
              </div>
            )}
          </>
        )}
      </div>
    </SellerLayout>
  );
}
