import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getProducts, getCategories } from '../../api/client';
import ProductCard from '../../components/ProductCard/ProductCard';
import { SkeletonCard, ErrorMessage, EmptyState } from '../../components/UI';
import '../pages.css';

export default function ShopPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSearch   = searchParams.get('search') ?? '';
  const initialCategory = searchParams.get('category') ?? '';
  const initialPage     = Number(searchParams.get('page') ?? 1);

  const [search,   setSearch]   = useState(initialSearch);
  const [category, setCategory] = useState(initialCategory);
  const [page,     setPage]     = useState(initialPage);

  const [data,       setData]       = useState(null);  // full paginated response
  const [categories, setCategories] = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);

  // Debounce search input
  const searchTimer = useRef(null);

  const load = useCallback(async (s, c, p) => {
    setLoading(true);
    setError(null);
    try {
      const [prodData, catData] = await Promise.all([
        getProducts({ search: s, category: c, page: p }),
        categories.length ? Promise.resolve({ categories }) : getCategories(),
      ]);
      setData(prodData);
      if (catData.categories) setCategories(catData.categories);
    } catch (err) {
      setError(err.message ?? 'Could not load products.');
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    load(search, category, page);
    setSearchParams(
      Object.fromEntries(
        [['search', search], ['category', category], ['page', String(page)]]
          .filter(([, v]) => v && v !== '1')
      )
    );
  }, [search, category, page]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSearchChange(e) {
    const val = e.target.value;
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setSearch(val);
      setPage(1);
    }, 400);
  }

  return (
    <div className="page-content">
      <div className="container">

        {/* Page header */}
        <div className="shop-header">
          <h1 className="heading-section">Our Bakery</h1>
          <p className="text-muted" style={{ marginTop: 'var(--sp-1)', fontSize: 'var(--text-sm)' }}>
            Browse fresh bakes from trusted local sellers
          </p>

          <div className="shop-controls">
            {/* Search */}
            <div className="shop-search">
              <span aria-hidden="true" style={{ color: 'var(--clr-text-subtle)' }}>🔍</span>
              <input
                id="shop-search-input"
                type="search"
                placeholder="Search cakes, breads, cookies…"
                defaultValue={initialSearch}
                onChange={handleSearchChange}
                aria-label="Search products"
              />
            </div>

            {/* Category filter */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-2)' }} role="group" aria-label="Category filter">
              <button
                className={`category-pill ${!category ? 'category-pill--active' : ''}`}
                onClick={() => { setCategory(''); setPage(1); }}
                aria-pressed={!category}
              >
                All
              </button>
              {categories.filter(c => c.code !== 'ALL').map(c => (
                <button
                  key={c.code}
                  className={`category-pill ${category === c.code ? 'category-pill--active' : ''}`}
                  onClick={() => { setCategory(c.code); setPage(1); }}
                  aria-pressed={category === c.code}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Results meta */}
        {data && !loading && (
          <p className="shop-results-meta">
            {data.count} product{data.count !== 1 ? 's' : ''} found
            {search ? ` for "${search}"` : ''}
          </p>
        )}

        {/* Error */}
        {error && <ErrorMessage message={error} onRetry={() => load(search, category, page)} />}

        {/* Loading */}
        {loading && (
          <div className="grid-products" aria-busy="true">
            {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        )}

        {/* Empty */}
        {!loading && !error && data?.results?.length === 0 && (
          <EmptyState
            icon="🍰"
            title="No products found"
            description={search ? `No results for "${search}". Try a different search.` : 'No products in this category yet.'}
            action={
              <button className="btn btn-secondary" onClick={() => { setSearch(''); setCategory(''); setPage(1); }}>
                Clear filters
              </button>
            }
          />
        )}

        {/* Grid */}
        {!loading && !error && data?.results?.length > 0 && (
          <div className="grid-products">
            {data.results.map(p => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        )}

        {/* Pagination */}
        {!loading && data && data.num_pages > 1 && (
          <nav className="shop-pagination" aria-label="Pagination">
            <button
              className="page-btn"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              aria-label="Previous page"
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
                  aria-label={`Page ${p}`}
                  aria-current={p === page ? 'page' : undefined}
                >
                  {p}
                </button>
              ))}

            <button
              className="page-btn"
              onClick={() => setPage(p => Math.min(data.num_pages, p + 1))}
              disabled={page >= data.num_pages}
              aria-label="Next page"
            >
              →
            </button>
          </nav>
        )}
      </div>
    </div>
  );
}
