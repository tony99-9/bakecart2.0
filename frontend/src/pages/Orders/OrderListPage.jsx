import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getB2BOrders, repeatB2BOrder } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { PageLoader, ErrorMessage, EmptyState } from '../../components/UI';
import '../Bakeries/Bakeries.css';
import './Orders.css';

export default function OrderListPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [orders, setOrders] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [repeatingId, setRepeatingId] = useState(null);

  useEffect(() => {
    fetchOrders();
  }, [user, statusFilter]);

  async function fetchOrders() {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getB2BOrders(statusFilter);
      setOrders(data.orders || []);
    } catch (err) {
      setError(err.message || 'Could not load orders.');
    } finally {
      setLoading(false);
    }
  }

  async function handleRepeatOrder(orderId) {
    setRepeatingId(orderId);
    try {
      const draft = await repeatB2BOrder(orderId);
      navigate('/wholesale-order', {
        state: { repeatOrderData: draft }
      });
    } catch (err) {
      alert(err.message || 'Could not repeat order.');
    } finally {
      setRepeatingId(null);
    }
  }

  function renderStatusBadge(st) {
    const map = {
      submitted: 'warning',
      pending: 'warning',
      confirmed: 'info',
      processing: 'info',
      in_preparation: 'info',
      dispatched: 'primary',
      shipped: 'primary',
      delivered: 'success',
      rejected: 'danger',
      cancelled: 'danger',
    };
    const badgeType = map[st] || 'info';
    return (
      <span className={`b2b-badge b2b-badge--${badgeType}`}>
        {st.replace('_', ' ')}
      </span>
    );
  }

  if (!user) {
    return (
      <div className="container" style={{ textAlign: 'center', padding: 'var(--sp-12) 0' }}>
        <p>Please log in as a dealer to view your wholesale orders.</p>
        <Link to="/login" className="btn btn-primary" style={{ marginTop: 'var(--sp-4)' }}>Log in</Link>
      </div>
    );
  }

  return (
    <div className="container" style={{ padding: 'var(--sp-8) 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--sp-4)', marginBottom: 'var(--sp-6)' }}>
        <div>
          <span className="b2b-badge b2b-badge--primary" style={{ marginBottom: 'var(--sp-2)' }}>
            Dealer Order Desk
          </span>
          <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 800, margin: 'var(--sp-1) 0' }}>
            Wholesale Purchase Orders
          </h1>
          <p style={{ color: 'var(--text-muted)' }}>
            Track order fulfillment, repeat past requisitions, and confirm delivery receipts.
          </p>
        </div>

        <div>
          <Link to="/wholesale-order" className="btn btn-primary">
            + New Purchase Order
          </Link>
        </div>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-6)', flexWrap: 'wrap' }}>
        {['', 'submitted', 'confirmed', 'in_preparation', 'dispatched', 'delivered', 'rejected'].map(st => (
          <button
            key={st}
            className={`btn btn-sm ${statusFilter === st ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setStatusFilter(st)}
          >
            {st ? st.replace('_', ' ').toUpperCase() : 'ALL ORDERS'}
          </button>
        ))}
      </div>

      {loading && <PageLoader />}
      {error && <ErrorMessage message={error} onRetry={fetchOrders} />}

      {!loading && !error && orders.length === 0 && (
        <EmptyState
          icon="📋"
          title="No Orders Found"
          message="You have no wholesale purchase orders matching this filter."
          action={<Link to="/bakeries" className="btn btn-primary">Browse Bakery Catalogues</Link>}
        />
      )}

      {!loading && !error && orders.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
          {orders.map(order => {
            const dateStr = new Date(order.created_at).toLocaleDateString(undefined, {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            });

            return (
              <div
                key={order.id}
                style={{
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-lg)',
                  padding: 'var(--sp-6)',
                  boxShadow: 'var(--shadow-xs)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--sp-4)', marginBottom: 'var(--sp-4)', borderBottom: '1px solid var(--border)', paddingBottom: 'var(--sp-3)' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
                      <span style={{ fontSize: 'var(--text-lg)', fontWeight: 800 }}>
                        PO #{order.id}
                      </span>
                      {renderStatusBadge(order.order_status)}
                    </div>
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Bakery: <strong>{order.bakery?.name || 'Artisan Bakery'}</strong> • Submitted: {dateStr}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 'var(--text-xl)', fontWeight: 800, color: 'var(--primary-dark)' }}>
                      €{order.total_amount}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                      {order.items?.length || 0} product lines
                    </div>
                  </div>
                </div>

                {order.order_status === 'rejected' && order.rejection_reason && (
                  <div style={{ background: '#fce8e6', border: '1px solid #f28b82', color: '#c5221f', borderRadius: 'var(--radius-md)', padding: 'var(--sp-3)', marginBottom: 'var(--sp-4)', fontSize: 'var(--text-sm)' }}>
                    <strong>Rejection Reason:</strong> {order.rejection_reason}
                  </div>
                )}

                {order.dispatch_notes && (
                  <div style={{ background: '#e8f0fe', border: '1px solid #aecbfa', color: '#1a73e8', borderRadius: 'var(--radius-md)', padding: 'var(--sp-3)', marginBottom: 'var(--sp-4)', fontSize: 'var(--text-sm)' }}>
                    <strong>Dispatch Notes:</strong> {order.dispatch_notes}
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
                  {order.items?.map(it => (
                    <div key={it.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)' }}>
                      <span>
                        <strong>{it.quantity}</strong> × {it.title_at_purchase} ({it.unit_at_purchase})
                      </span>
                      <span>€{it.subtotal}</span>
                    </div>
                  ))}
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--sp-3)', borderTop: '1px solid var(--border)', paddingTop: 'var(--sp-3)' }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={repeatingId === order.id}
                    onClick={() => handleRepeatOrder(order.id)}
                  >
                    {repeatingId === order.id ? 'Loading...' : '🔄 Repeat Order'}
                  </button>
                  <Link to={`/orders/${order.id}`} className="btn btn-primary btn-sm">
                    View Tracking Details →
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
