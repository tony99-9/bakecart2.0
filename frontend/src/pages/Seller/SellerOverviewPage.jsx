import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getSellerSummary } from '../../api/client';
import { PageLoader, ErrorMessage } from '../../components/UI';
import SellerLayout from './SellerLayout';

export default function SellerOverviewPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    async function loadSummary() {
      setLoading(true);
      setError(null);
      try {
        const res = await getSellerSummary();
        if (isMounted) setSummary(res.summary);
      } catch (err) {
        if (isMounted) setError(err.message ?? 'Could not load sales summary.');
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadSummary();
    return () => { isMounted = false; };
  }, []);

  if (loading) return <SellerLayout><PageLoader /></SellerLayout>;

  return (
    <SellerLayout>
      {error && <ErrorMessage message={error} onRetry={() => window.location.reload()} />}

      {summary && (
        <>
          {/* Metrics summary cards */}
          <div className="metrics-grid">
            <div className="metric-card">
              <span className="metric-card__label">Total Revenue</span>
              <span className="metric-card__value">
                €{Number(summary.total_sales).toFixed(2)}
              </span>
              <span className="metric-card__sub">From completed & paid orders</span>
            </div>

            <div className="metric-card">
              <span className="metric-card__label">Units Sold</span>
              <span className="metric-card__value">{summary.total_units_sold}</span>
              <span className="metric-card__sub">Individual bakes delivered</span>
            </div>

            <div className="metric-card">
              <span className="metric-card__label">Total Orders</span>
              <span className="metric-card__value">{summary.total_orders}</span>
              <span className="metric-card__sub">
                {summary.pending_orders} pending • {summary.processing_orders} processing
              </span>
            </div>

            <div className="metric-card">
              <span className="metric-card__label">Catalogue Size</span>
              <span className="metric-card__value">{summary.total_products}</span>
              <span className="metric-card__sub">
                {summary.active_products} active • {summary.out_of_stock_products} out of stock
              </span>
            </div>
          </div>

          {/* Quick Actions / Status Overview */}
          <div className="data-table-card" style={{ padding: 'var(--sp-6)', marginBottom: 'var(--sp-8)' }}>
            <h2 className="heading-section" style={{ fontSize: 'var(--text-lg)', marginBottom: 'var(--sp-4)' }}>
              Operational Status
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--sp-4)' }}>
              <div style={{ padding: 'var(--sp-4)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)' }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-muted)' }}>Pending Orders</span>
                <p style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, margin: 'var(--sp-1) 0', color: summary.pending_orders > 0 ? '#e65100' : 'var(--clr-text)' }}>
                  {summary.pending_orders}
                </p>
                {summary.pending_orders > 0 ? (
                  <Link to="/seller/orders" className="btn btn-primary btn-sm">Process Orders →</Link>
                ) : (
                  <span style={{ fontSize: 'var(--text-xs)', color: '#2e7d32' }}>✓ All caught up</span>
                )}
              </div>

              <div style={{ padding: 'var(--sp-4)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)' }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-muted)' }}>In the Oven (Processing)</span>
                <p style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, margin: 'var(--sp-1) 0', color: '#0277bd' }}>
                  {summary.processing_orders}
                </p>
                <Link to="/seller/orders" className="text-muted" style={{ fontSize: 'var(--text-xs)' }}>View queue →</Link>
              </div>

              <div style={{ padding: 'var(--sp-4)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)' }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-muted)' }}>Shipped / Delivered</span>
                <p style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, margin: 'var(--sp-1) 0', color: '#2e7d32' }}>
                  {summary.shipped_orders}
                </p>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-muted)' }}>Completed fulfillments</span>
              </div>
            </div>
          </div>
        </>
      )}
    </SellerLayout>
  );
}
