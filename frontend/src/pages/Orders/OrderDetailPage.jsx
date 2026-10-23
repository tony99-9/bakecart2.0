import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate, useLocation } from 'react-router-dom';
import { getB2BOrderDetail, confirmB2BReceipt, repeatB2BOrder } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { PageLoader, ErrorMessage } from '../../components/UI';
import '../Bakeries/Bakeries.css';
import './Orders.css';

export default function OrderDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmingReceipt, setConfirmingReceipt] = useState(false);
  const [repeating, setRepeating] = useState(false);

  const flashMessage = location.state?.flashMessage;

  useEffect(() => {
    loadOrder();
  }, [id]);

  async function loadOrder() {
    setLoading(true);
    setError(null);
    try {
      const res = await getB2BOrderDetail(id);
      setOrder(res.order);
    } catch (err) {
      setError(err.message || 'Could not load order details.');
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmReceipt() {
    if (!window.confirm('Confirm that this wholesale delivery has arrived in good condition?')) return;
    setConfirmingReceipt(true);
    try {
      await confirmB2BReceipt(order.id);
      await loadOrder();
    } catch (err) {
      alert(err.message || 'Failed to confirm delivery receipt.');
    } finally {
      setConfirmingReceipt(false);
    }
  }

  async function handleRepeatOrder() {
    setRepeating(true);
    try {
      const draft = await repeatB2BOrder(order.id);
      navigate('/wholesale-order', {
        state: { repeatOrderData: draft }
      });
    } catch (err) {
      alert(err.message || 'Could not repeat order.');
    } finally {
      setRepeating(false);
    }
  }

  if (loading) return <PageLoader />;
  if (error || !order) {
    return (
      <div className="container" style={{ padding: 'var(--sp-8) 0' }}>
        <ErrorMessage message={error || 'Order not found.'} onRetry={loadOrder} />
        <div style={{ marginTop: 'var(--sp-4)' }}>
          <Link to="/orders" className="btn btn-secondary">← Back to Orders</Link>
        </div>
      </div>
    );
  }

  // Stepper calculations
  const steps = [
    { key: 'submitted', label: '1. Submitted' },
    { key: 'confirmed', label: '2. Confirmed' },
    { key: 'in_preparation', label: '3. In Preparation' },
    { key: 'dispatched', label: '4. Dispatched' },
    { key: 'delivered', label: '5. Delivered' },
  ];

  const statusOrder = ['submitted', 'confirmed', 'in_preparation', 'dispatched', 'delivered'];
  const currentIdx = statusOrder.indexOf(order.order_status);
  const isRejected = order.order_status === 'rejected';

  return (
    <div className="container" style={{ padding: 'var(--sp-8) 0', maxWidth: '880px' }}>
      <Link to="/orders" style={{ fontSize: 'var(--text-sm)', color: 'var(--primary)', fontWeight: 600 }}>
        ← Back to Purchase Orders
      </Link>

      {flashMessage && (
        <div style={{ background: '#e6f4ea', border: '1px solid #34a853', color: '#137333', padding: 'var(--sp-4)', borderRadius: 'var(--radius-md)', margin: 'var(--sp-4) 0', fontWeight: 600 }}>
          ✓ {flashMessage}
        </div>
      )}

      {/* Header Card */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 'var(--sp-6)', margin: 'var(--sp-4) 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--sp-4)' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
              <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, margin: 0 }}>
                Wholesale Order PO #{order.id}
              </h1>
              <span className={`b2b-badge b2b-badge--${isRejected ? 'danger' : order.order_status === 'delivered' ? 'success' : 'primary'}`}>
                {order.order_status.replace('_', ' ').toUpperCase()}
              </span>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginTop: '4px' }}>
              Submitted on {new Date(order.created_at).toLocaleString()}
            </p>
          </div>

          <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
            <button
              className="btn btn-secondary btn-sm"
              disabled={repeating}
              onClick={handleRepeatOrder}
            >
              {repeating ? 'Preparing...' : '🔄 Repeat This Order'}
            </button>
            {(order.order_status === 'dispatched' || order.order_status === 'shipped') && (
              <button
                className="btn btn-primary btn-sm"
                disabled={confirmingReceipt}
                onClick={handleConfirmReceipt}
              >
                {confirmingReceipt ? 'Confirming...' : '✓ Confirm Goods Received'}
              </button>
            )}
          </div>
        </div>

        {/* Stepper (if not rejected) */}
        {!isRejected ? (
          <div className="order-stepper">
            {steps.map((st, i) => {
              const isCompleted = currentIdx > i;
              const isActive = currentIdx === i;
              return (
                <div key={st.key} className={`order-step ${isCompleted ? 'order-step--completed' : isActive ? 'order-step--active' : ''}`}>
                  <div className="order-step__circle">
                    {isCompleted ? '✓' : i + 1}
                  </div>
                  <span className="order-step__label">{st.label}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ background: '#fce8e6', border: '1px solid #f28b82', color: '#c5221f', borderRadius: 'var(--radius-md)', padding: 'var(--sp-4)', margin: 'var(--sp-6) 0' }}>
            <strong style={{ fontSize: 'var(--text-base)' }}>Order Rejected by Bakery</strong>
            <p style={{ margin: '4px 0 0 0', fontSize: 'var(--text-sm)' }}>
              <strong>Reason:</strong> {order.rejection_reason || 'Capacity or ingredient constraints.'}
            </p>
          </div>
        )}

        {/* Dispatch Notes Banner */}
        {order.dispatch_notes && (
          <div style={{ background: '#e8f0fe', border: '1px solid #aecbfa', color: '#1a73e8', borderRadius: 'var(--radius-md)', padding: 'var(--sp-4)', marginBottom: 'var(--sp-4)', fontSize: 'var(--text-sm)' }}>
            <strong>🚚 Dispatch & Logistics Notes:</strong>
            <p style={{ margin: '4px 0 0 0' }}>{order.dispatch_notes}</p>
          </div>
        )}

        {/* Parties Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 'var(--sp-6)', paddingTop: 'var(--sp-4)', borderTop: '1px solid var(--border)' }}>
          <div>
            <h3 style={{ fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700 }}>
              Supplying Bakery
            </h3>
            <div style={{ fontWeight: 700, fontSize: 'var(--text-base)', marginTop: '4px' }}>
              {order.bakery?.name}
            </div>
            {order.bakery?.phone && <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>📞 {order.bakery.phone}</div>}
            {order.bakery?.email && <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>✉️ {order.bakery.email}</div>}
            {order.bakery?.address && <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>📍 {order.bakery.address}</div>}
          </div>

          <div>
            <h3 style={{ fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700 }}>
              Purchasing Dealer
            </h3>
            <div style={{ fontWeight: 700, fontSize: 'var(--text-base)', marginTop: '4px' }}>
              {order.dealer?.business_name || order.dealer?.username}
            </div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
              Contact: {order.dealer?.contact_name || order.dealer?.username}
            </div>
            {order.dealer?.phone && <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>📞 {order.dealer.phone}</div>}
            {order.dealer?.delivery_address && (
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
                📍 Delivery to: {order.dealer.delivery_address}
              </div>
            )}
          </div>
        </div>

        {order.notes && (
          <div style={{ marginTop: 'var(--sp-4)', paddingTop: 'var(--sp-3)', borderTop: '1px dashed var(--border)', fontSize: 'var(--text-sm)' }}>
            <strong>Dealer Delivery Instructions:</strong> {order.notes}
          </div>
        )}
      </div>

      {/* Line Items Table */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 'var(--sp-6)' }}>
        <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, marginBottom: 'var(--sp-4)' }}>
          Order Items & Pricing Snapshot
        </h2>

        <div style={{ overflowX: 'auto' }}>
          <table className="wholesale-table">
            <thead>
              <tr>
                <th>Product Line</th>
                <th>Packaging Unit</th>
                <th>Unit Price (Wholesale)</th>
                <th>Quantity</th>
                <th style={{ textAlign: 'right' }}>Subtotal</th>
              </tr>
            </thead>
            <tbody>
              {order.items?.map(it => (
                <tr key={it.id}>
                  <td><strong>{it.title_at_purchase}</strong></td>
                  <td>{it.unit_at_purchase}</td>
                  <td>€{it.unit_price_at_purchase}</td>
                  <td><strong>{it.quantity}</strong></td>
                  <td style={{ textAlign: 'right' }}><strong>€{it.subtotal}</strong></td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan="4" style={{ textAlign: 'right', fontWeight: 800, fontSize: 'var(--text-base)' }}>
                  Total Wholesale Order Amount:
                </td>
                <td style={{ textAlign: 'right', fontWeight: 800, fontSize: 'var(--text-xl)', color: 'var(--primary-dark)' }}>
                  €{order.total_amount}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
}
