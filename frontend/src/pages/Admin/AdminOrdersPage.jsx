import { useState, useEffect, useCallback } from 'react';
import { getAdminOrders } from '../../api/client';
import { PageLoader, ErrorMessage } from '../../components/UI';
import AdminLayout from './AdminLayout';

export default function AdminOrdersPage() {
  const [orders, setOrders] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [paymentFilter, setPaymentFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminOrders();
      setOrders(res.orders ?? []);
    } catch (err) {
      setError(err.message ?? 'Could not load orders.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filteredOrders = orders.filter(o => {
    if (statusFilter && o.order_status !== statusFilter) return false;
    if (paymentFilter && o.payment_status !== paymentFilter) return false;
    return true;
  });

  return (
    <AdminLayout>
      <div className="data-table-card">
        {/* Filter Bar */}
        <div className="admin-filter-bar">
          <div style={{ display: 'flex', gap: 'var(--sp-4)', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
              <label htmlFor="admin-order-status" style={{ fontSize: 'var(--text-sm)', color: 'var(--clr-text-muted)' }}>
                Fulfillment Status:
              </label>
              <select
                id="admin-order-status"
                className="admin-select"
                value={statusFilter}
                onChange={e => setStatusFilter(e.target.value)}
              >
                <option value="">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="processing">Processing</option>
                <option value="shipped">Shipped</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
              <label htmlFor="admin-order-payment" style={{ fontSize: 'var(--text-sm)', color: 'var(--clr-text-muted)' }}>
                Payment Status:
              </label>
              <select
                id="admin-order-payment"
                className="admin-select"
                value={paymentFilter}
                onChange={e => setPaymentFilter(e.target.value)}
              >
                <option value="">All Payments</option>
                <option value="paid">Paid</option>
                <option value="unpaid">Unpaid</option>
                <option value="refunded">Refunded</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          </div>

          <span className="text-muted" style={{ fontSize: 'var(--text-xs)', marginLeft: 'auto' }}>
            Showing {filteredOrders.length} of {orders.length} orders
          </span>
        </div>

        {error && <ErrorMessage message={error} onRetry={load} />}

        {loading ? (
          <PageLoader />
        ) : filteredOrders.length === 0 ? (
          <div style={{ padding: 'var(--sp-12)', textAlign: 'center', color: 'var(--clr-text-muted)' }}>
            No orders match the selected filters.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order #</th>
                  <th>Buyer</th>
                  <th>Items Purchased</th>
                  <th>Total Amount</th>
                  <th>Order Status</th>
                  <th>Payment</th>
                  <th>Placed Date</th>
                </tr>
              </thead>
              <tbody>
                {filteredOrders.map(order => {
                  const dateStr = new Date(order.created_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  });

                  return (
                    <tr key={order.id}>
                      <td>
                        <strong>#{order.id}</strong>
                      </td>

                      <td>
                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--clr-text)' }}>
                          {order.buyer_username || 'Anonymous'}
                        </span>
                      </td>

                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          {order.items?.map(i => (
                            <span key={i.id} style={{ fontSize: 'var(--text-xs)' }}>
                              {i.quantity}× {i.title_at_purchase} (€{Number(i.subtotal).toFixed(2)})
                            </span>
                          ))}
                        </div>
                      </td>

                      <td>
                        <strong>€{Number(order.total_amount).toFixed(2)}</strong>
                      </td>

                      <td>
                        <span className={`status-pill status-pill--${order.order_status}`}>
                          {order.order_status}
                        </span>
                      </td>

                      <td>
                        <span className={`status-pill status-pill--${order.payment_status}`}>
                          {order.payment_status}
                        </span>
                      </td>

                      <td style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-muted)' }}>
                        {dateStr}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
