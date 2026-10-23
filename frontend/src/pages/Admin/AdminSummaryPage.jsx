import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getAdminSummary } from '../../api/client';
import { PageLoader, ErrorMessage } from '../../components/UI';
import AdminLayout from './AdminLayout';

export default function AdminSummaryPage() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    async function fetchSummary() {
      setLoading(true);
      setError(null);
      try {
        const res = await getAdminSummary();
        if (isMounted) setMetrics(res.metrics);
      } catch (err) {
        if (isMounted) setError(err.message ?? 'Could not load admin summary metrics.');
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    fetchSummary();
    return () => { isMounted = false; };
  }, []);

  if (loading) return <AdminLayout><PageLoader /></AdminLayout>;

  return (
    <AdminLayout>
      {error && <ErrorMessage message={error} onRetry={() => window.location.reload()} />}

      {metrics && (
        <>
          {/* Top-Level KPI Grid */}
          <div className="metrics-grid">
            <div className="metric-card">
              <span className="metric-card__label">Gross Platform Revenue</span>
              <span className="metric-card__value">
                €{Number(metrics.total_revenue).toFixed(2)}
              </span>
              <span className="metric-card__sub">{metrics.paid_orders_count} paid orders</span>
            </div>

            <div className="metric-card">
              <span className="metric-card__label">Total Orders</span>
              <span className="metric-card__value">{metrics.total_orders}</span>
              <span className="metric-card__sub">
                {metrics.pending_orders} pending • {metrics.processing_orders} processing
              </span>
            </div>

            <div className="metric-card">
              <span className="metric-card__label">Marketplace Products</span>
              <span className="metric-card__value">{metrics.total_products}</span>
              <span className="metric-card__sub">
                {metrics.active_products} active • {metrics.inactive_products} deactivated
              </span>
            </div>

            <div className="metric-card">
              <span className="metric-card__label">Registered Accounts</span>
              <span className="metric-card__value">{metrics.total_users}</span>
              <span className="metric-card__sub">
                {metrics.sellers_count} sellers • {metrics.buyers_count} buyers
              </span>
            </div>
          </div>

          {/* Breakdown Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--sp-6)' }}>
            {/* Orders Fulfillment Distribution */}
            <div className="data-table-card" style={{ padding: 'var(--sp-6)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-4)' }}>
                <h2 className="heading-section" style={{ fontSize: 'var(--text-lg)' }}>
                  Order Status Breakdown
                </h2>
                <Link to="/admin/orders" className="text-muted" style={{ fontSize: 'var(--text-xs)' }}>
                  View All Orders →
                </Link>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--sp-3)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)' }}>
                  <span>⏳ Pending Orders</span>
                  <strong>{metrics.pending_orders}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--sp-3)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)' }}>
                  <span>🥣 In Preparation (Processing)</span>
                  <strong>{metrics.processing_orders}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--sp-3)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)' }}>
                  <span>🚚 Shipped / Fulfilled</span>
                  <strong>{metrics.shipped_orders}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--sp-3)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)' }}>
                  <span>❌ Cancelled Orders</span>
                  <strong>{metrics.cancelled_orders}</strong>
                </div>
              </div>
            </div>

            {/* User Roles & Product Status */}
            <div className="data-table-card" style={{ padding: 'var(--sp-6)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-4)' }}>
                <h2 className="heading-section" style={{ fontSize: 'var(--text-lg)' }}>
                  Community & Catalogue
                </h2>
                <Link to="/admin/users" className="text-muted" style={{ fontSize: 'var(--text-xs)' }}>
                  Manage Users →
                </Link>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--sp-3)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)' }}>
                  <span>🏪 Active Sellers</span>
                  <strong>{metrics.sellers_count}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--sp-3)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)' }}>
                  <span>👤 Registered Buyers</span>
                  <strong>{metrics.buyers_count}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--sp-3)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)' }}>
                  <span>🛡️ Staff Administrators</span>
                  <strong>{metrics.admins_count}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--sp-3)', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-md)' }}>
                  <span>🍰 Listed Active Products</span>
                  <strong style={{ color: '#2e7d32' }}>{metrics.active_products}</strong>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </AdminLayout>
  );
}
