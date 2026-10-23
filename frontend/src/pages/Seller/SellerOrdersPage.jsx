import { useState, useEffect, useCallback } from 'react';
import { getBakeryIncomingOrders, actionBakeryOrder, ApiError } from '../../api/client';
import { PageLoader, ErrorMessage, EmptyState } from '../../components/UI';
import SellerLayout from './SellerLayout';
import '../Bakeries/Bakeries.css';

export default function SellerOrdersPage() {
  const [orders, setOrders] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionInProgress, setActionInProgress] = useState(false);

  // Modals state
  const [rejectModalOrder, setRejectModalOrder] = useState(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [dispatchModalOrder, setDispatchModalOrder] = useState(null);
  const [dispatchNotes, setDispatchNotes] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getBakeryIncomingOrders(statusFilter);
      setOrders(res.orders || []);
    } catch (err) {
      setError(err.message || 'Could not load bakery orders.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  async function handleAction(orderId, action, extra = {}) {
    setActionInProgress(true);
    setActionError(null);
    try {
      await actionBakeryOrder(orderId, { action, ...extra });
      setRejectModalOrder(null);
      setRejectionReason('');
      setDispatchModalOrder(null);
      setDispatchNotes('');
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Action failed.');
    } finally {
      setActionInProgress(false);
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
    };
    return (
      <span className={`b2b-badge b2b-badge--${map[st] || 'info'}`}>
        {st.replace('_', ' ')}
      </span>
    );
  }

  return (
    <SellerLayout>
      <div className="data-table-card">
        <div className="data-table-toolbar" style={{ flexWrap: 'wrap', gap: 'var(--sp-4)' }}>
          <div>
            <h2 className="heading-section" style={{ fontSize: 'var(--text-lg)', margin: 0 }}>
              Incoming Dealer Orders & Dispatch Desk
            </h2>
            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
              Review purchase orders from wholesale dealers, accept/reject batches, and manage delivery dispatches.
            </p>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
            ↻ Refresh
          </button>
        </div>

        {/* Status Filters */}
        <div style={{ display: 'flex', gap: 'var(--sp-2)', padding: 'var(--sp-4)', borderBottom: '1px solid var(--border)', flexWrap: 'wrap' }}>
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

        {actionError && <div style={{ padding: 'var(--sp-4)' }}><ErrorMessage message={actionError} /></div>}
        {error && <div style={{ padding: 'var(--sp-4)' }}><ErrorMessage message={error} onRetry={load} /></div>}

        {loading ? (
          <PageLoader />
        ) : orders.length === 0 ? (
          <EmptyState
            icon="📋"
            title="No orders found"
            description="When wholesale dealers submit purchase orders for your bakery, they will appear here."
          />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>PO #</th>
                  <th>Dealer / Business</th>
                  <th>Order Items</th>
                  <th>Total Amount</th>
                  <th>Status</th>
                  <th>Order Date</th>
                  <th style={{ textAlign: 'right' }}>Wholesale Action</th>
                </tr>
              </thead>
              <tbody>
                {orders.map(order => {
                  const dateStr = new Date(order.created_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  });
                  const isSubmitted = order.order_status === 'submitted' || order.order_status === 'pending';
                  const isConfirmed = order.order_status === 'confirmed' || order.order_status === 'processing';
                  const isInPrep = order.order_status === 'in_preparation';
                  const isDispatched = order.order_status === 'dispatched' || order.order_status === 'shipped';

                  return (
                    <tr key={order.id}>
                      <td>
                        <strong>PO #{order.id}</strong>
                      </td>

                      <td>
                        <div>
                          <strong>{order.dealer?.business_name || order.dealer?.username}</strong>
                          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                            Contact: {order.dealer?.contact_name}
                          </div>
                          {order.dealer?.phone && (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                              📞 {order.dealer.phone}
                            </div>
                          )}
                          {order.dealer?.delivery_address && (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                              📍 {order.dealer.delivery_address}
                            </div>
                          )}
                        </div>
                      </td>

                      <td>
                        <div style={{ fontSize: 'var(--text-xs)', maxWidth: '280px' }}>
                          {order.items?.map(it => (
                            <div key={it.id} style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', margin: '2px 0' }}>
                              <span><strong>{it.quantity}</strong> × {it.title_at_purchase} ({it.unit_at_purchase})</span>
                              <span>€{it.subtotal}</span>
                            </div>
                          ))}
                          {order.notes && (
                            <div style={{ marginTop: '4px', color: 'var(--primary-dark)', fontStyle: 'italic' }}>
                              Note: "{order.notes}"
                            </div>
                          )}
                        </div>
                      </td>

                      <td>
                        <strong style={{ fontSize: 'var(--text-base)', color: 'var(--primary-dark)' }}>
                          €{order.total_amount}
                        </strong>
                      </td>

                      <td>
                        {renderStatusBadge(order.order_status)}
                        {order.rejection_reason && (
                          <div style={{ fontSize: '10px', color: '#c5221f', marginTop: '4px' }}>
                            {order.rejection_reason}
                          </div>
                        )}
                        {order.dispatch_notes && (
                          <div style={{ fontSize: '10px', color: '#1a73e8', marginTop: '4px' }}>
                            {order.dispatch_notes}
                          </div>
                        )}
                      </td>

                      <td style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                        {dateStr}
                      </td>

                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--sp-2)', flexWrap: 'wrap' }}>
                          {isSubmitted && (
                            <>
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                disabled={actionInProgress}
                                onClick={() => handleAction(order.id, 'confirm')}
                              >
                                ✓ Confirm
                              </button>
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                style={{ color: '#c5221f' }}
                                disabled={actionInProgress}
                                onClick={() => setRejectModalOrder(order)}
                              >
                                ✕ Reject
                              </button>
                            </>
                          )}

                          {isConfirmed && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              disabled={actionInProgress}
                              onClick={() => handleAction(order.id, 'prepare')}
                            >
                              👨‍🍳 In Preparation →
                            </button>
                          )}

                          {(isConfirmed || isInPrep) && (
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              disabled={actionInProgress}
                              onClick={() => setDispatchModalOrder(order)}
                            >
                              🚚 Dispatch →
                            </button>
                          )}

                          {isDispatched && (
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                              Awaiting dealer receipt
                            </span>
                          )}

                          {order.order_status === 'delivered' && (
                            <span style={{ fontSize: 'var(--text-xs)', color: '#137333', fontWeight: 600 }}>
                              ✓ Completed
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Reject Modal */}
      {rejectModalOrder && (
        <div className="action-modal-overlay">
          <div className="action-modal animate-scale-in">
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 800, margin: '0 0 var(--sp-2) 0' }}>
              Reject Purchase Order #{rejectModalOrder.id}
            </h3>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', margin: '0 0 var(--sp-4) 0' }}>
              Rejecting this order will automatically restore reserved stock to your inventory and notify the dealer.
            </p>

            <div className="form-group" style={{ marginBottom: 'var(--sp-4)' }}>
              <label className="form-label" style={{ fontWeight: 600 }}>Reason for Rejection (Required)</label>
              <textarea
                className="form-control"
                rows="3"
                placeholder="e.g. Insufficient organic rye flour for batch production; oven maintenance..."
                value={rejectionReason}
                onChange={e => setRejectionReason(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--sp-2)' }}>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => { setRejectModalOrder(null); setRejectionReason(''); }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ background: '#c5221f', borderColor: '#c5221f' }}
                disabled={actionInProgress || !rejectionReason.trim()}
                onClick={() => handleAction(rejectModalOrder.id, 'reject', { rejection_reason: rejectionReason })}
              >
                {actionInProgress ? 'Rejecting...' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Dispatch Modal */}
      {dispatchModalOrder && (
        <div className="action-modal-overlay">
          <div className="action-modal animate-scale-in">
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 800, margin: '0 0 var(--sp-2) 0' }}>
              Dispatch Purchase Order #{dispatchModalOrder.id}
            </h3>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', margin: '0 0 var(--sp-4) 0' }}>
              Deliver to: <strong>{dispatchModalOrder.dealer?.delivery_address || 'Dealer address'}</strong>
            </p>

            <div className="form-group" style={{ marginBottom: 'var(--sp-4)' }}>
              <label className="form-label" style={{ fontWeight: 600 }}>Dispatch & Carrier Notes</label>
              <textarea
                className="form-control"
                rows="3"
                placeholder="e.g. Van #3, Driver: George, Estimated arrival 6:45 AM..."
                value={dispatchNotes}
                onChange={e => setDispatchNotes(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--sp-2)' }}>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => { setDispatchModalOrder(null); setDispatchNotes(''); }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={actionInProgress}
                onClick={() => handleAction(dispatchModalOrder.id, 'dispatch', { dispatch_notes: dispatchNotes })}
              >
                {actionInProgress ? 'Dispatching...' : 'Confirm Dispatch'}
              </button>
            </div>
          </div>
        </div>
      )}
    </SellerLayout>
  );
}
