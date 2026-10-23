import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getB2BBakeries, getB2BBakeryCatalogue, createB2BOrder } from '../../api/client';
import { PageLoader, ErrorMessage } from '../../components/UI';
import { useAuth } from '../../context/AuthContext';
import '../Bakeries/Bakeries.css';

export default function WholesaleOrderDeskPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  const [bakeries, setBakeries] = useState([]);
  const [selectedBakeryId, setSelectedBakeryId] = useState('');
  const [catalogue, setCatalogue] = useState([]);
  const [quantities, setQuantities] = useState({});
  const [notes, setNotes] = useState('');
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [submitError, setSubmitError] = useState(null);

  // Check if we arrived here from a "Repeat Order" action
  const repeatData = location.state?.repeatOrderData;

  useEffect(() => {
    async function init() {
      try {
        const bRes = await getB2BBakeries();
        const list = bRes.bakeries || [];
        setBakeries(list);

        if (repeatData?.bakery_id) {
          setSelectedBakeryId(String(repeatData.bakery_id));
          await loadBakeryCatalogue(repeatData.bakery_id, repeatData.items);
          if (repeatData.notes) setNotes(repeatData.notes);
        } else if (list.length > 0) {
          setSelectedBakeryId(String(list[0].id));
          await loadBakeryCatalogue(list[0].id);
        }
      } catch (err) {
        setError(err.message || 'Could not load order desk.');
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  useEffect(() => {
    if (user?.dealer_profile?.delivery_address) {
      setDeliveryAddress(user.dealer_profile.delivery_address);
    }
  }, [user]);

  async function loadBakeryCatalogue(bakeryId, prefillItems = []) {
    try {
      const res = await getB2BBakeryCatalogue(bakeryId);
      const prods = res.products || [];
      setCatalogue(prods);

      const qMap = {};
      prods.forEach(p => {
        const matched = prefillItems.find(it => it.product_id === p.id);
        qMap[p.id] = matched ? matched.quantity : 0;
      });
      setQuantities(qMap);
    } catch (err) {
      setError(err.message || 'Failed to load catalogue.');
    }
  }

  function handleBakeryChange(e) {
    const newId = e.target.value;
    setSelectedBakeryId(newId);
    if (newId) {
      loadBakeryCatalogue(newId);
    } else {
      setCatalogue([]);
      setQuantities({});
    }
  }

  function handleQuantityChange(productId, val) {
    const num = Math.max(0, parseInt(val, 10) || 0);
    setQuantities(prev => ({ ...prev, [productId]: num }));
  }

  const orderLines = catalogue
    .filter(p => (quantities[p.id] || 0) > 0)
    .map(p => ({
      product: p,
      quantity: quantities[p.id],
      subtotal: (parseFloat(p.price) * quantities[p.id]).toFixed(2),
      isUnderMOQ: quantities[p.id] < p.min_order_quantity,
      isOverStock: quantities[p.id] > p.quantity,
    }));

  const total = orderLines.reduce((acc, l) => acc + parseFloat(l.subtotal), 0).toFixed(2);
  const hasErrors = orderLines.some(l => l.isUnderMOQ || l.isOverStock);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!user) {
      navigate('/login');
      return;
    }
    if (orderLines.length === 0) {
      setSubmitError('Please specify quantities for at least one item.');
      return;
    }
    if (hasErrors) {
      setSubmitError('Please correct quantities before submitting.');
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      const res = await createB2BOrder({
        bakery_id: parseInt(selectedBakeryId, 10),
        items: orderLines.map(l => ({
          product_id: l.product.id,
          quantity: l.quantity,
        })),
        notes,
        delivery_address: deliveryAddress,
      });
      navigate(`/orders/${res.order.id}`, {
        state: { flashMessage: 'Wholesale Purchase Order Submitted!' }
      });
    } catch (err) {
      setSubmitError(err.message || 'Failed to submit order.');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <PageLoader />;
  if (error) return <div className="container" style={{ padding: 'var(--sp-8) 0' }}><ErrorMessage message={error} /></div>;

  return (
    <div className="container" style={{ padding: 'var(--sp-8) 0' }}>
      <div style={{ marginBottom: 'var(--sp-6)' }}>
        <span className="b2b-badge b2b-badge--primary" style={{ marginBottom: 'var(--sp-2)' }}>
          Wholesale Order Desk
        </span>
        <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 800, margin: 'var(--sp-1) 0' }}>
          Bakery Purchase Order Entry
        </h1>
        <p style={{ color: 'var(--text-muted)' }}>
          Quickly compile and submit wholesale replenishment orders to your supplying dealers.
        </p>
      </div>

      {repeatData?.warnings?.length > 0 && (
        <div style={{ background: '#fef7e0', border: '1px solid #f9ab00', borderRadius: 'var(--radius-md)', padding: 'var(--sp-4)', marginBottom: 'var(--sp-4)', color: '#b06000', fontSize: 'var(--text-sm)' }}>
          <strong>Repeat Order Notice:</strong>
          <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
            {repeatData.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 'var(--sp-6)', marginBottom: 'var(--sp-6)' }}>
        <label className="form-label" style={{ fontWeight: 700 }}>Select Supplying Bakery</label>
        <select
          className="form-control"
          value={selectedBakeryId}
          onChange={handleBakeryChange}
          style={{ maxWidth: '400px' }}
        >
          {bakeries.map(b => (
            <option key={b.id} value={b.id}>
              {b.name} ({b.products_count} lines)
            </option>
          ))}
        </select>
      </div>

      <div className="catalogue-layout">
        <div>
          <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, marginBottom: 'var(--sp-4)' }}>
            Available Wholesale Lines ({catalogue.length})
          </h2>

          <div style={{ overflowX: 'auto' }}>
            <table className="wholesale-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Wholesale Unit</th>
                  <th>Unit Price</th>
                  <th>MOQ</th>
                  <th>Stock</th>
                  <th style={{ width: '120px' }}>Order Quantity</th>
                  <th>Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {catalogue.map(p => {
                  const qty = quantities[p.id] || 0;
                  const isUnderMOQ = qty > 0 && qty < p.min_order_quantity;
                  const isOverStock = qty > p.quantity;
                  const lineTotal = (parseFloat(p.price) * qty).toFixed(2);

                  return (
                    <tr key={p.id}>
                      <td>
                        <strong>{p.title}</strong>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>{p.category_label}</div>
                      </td>
                      <td>{p.unit}</td>
                      <td><strong>€{p.price}</strong></td>
                      <td><span className="b2b-badge b2b-badge--warning">{p.min_order_quantity}</span></td>
                      <td>{p.quantity}</td>
                      <td>
                        <input
                          type="number"
                          className="form-control"
                          min="0"
                          max={p.quantity}
                          value={qty}
                          onChange={e => handleQuantityChange(p.id, e.target.value)}
                          style={{ textAlign: 'center', borderColor: (isUnderMOQ || isOverStock) ? '#c5221f' : undefined }}
                        />
                        {isUnderMOQ && <div style={{ color: '#c5221f', fontSize: '10px' }}>Min {p.min_order_quantity}</div>}
                        {isOverStock && <div style={{ color: '#c5221f', fontSize: '10px' }}>Max {p.quantity}</div>}
                      </td>
                      <td>
                        <strong>€{lineTotal}</strong>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <aside>
          <div className="order-sheet-card">
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, marginBottom: 'var(--sp-4)' }}>
              Order Breakdown
            </h3>

            {orderLines.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
                Enter quantities above to formulate your wholesale purchase order.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
                {orderLines.map(l => (
                  <div key={l.product.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)' }}>
                    <span>{l.quantity} × {l.product.title}</span>
                    <strong>€{l.subtotal}</strong>
                  </div>
                ))}
                <div style={{ borderTop: '1px dashed var(--border)', paddingTop: 'var(--sp-3)', display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-lg)', fontWeight: 800 }}>
                  <span>Order Total</span>
                  <span style={{ color: 'var(--primary-dark)' }}>€{total}</span>
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit} style={{ marginTop: 'var(--sp-4)' }}>
              <div className="form-group" style={{ marginBottom: 'var(--sp-3)' }}>
                <label className="form-label" style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>Delivery Instructions</label>
                <textarea
                  className="form-control"
                  rows="2"
                  placeholder="Special instructions for bakery driver..."
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  style={{ fontSize: 'var(--text-sm)' }}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 'var(--sp-4)' }}>
                <label className="form-label" style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>Delivery Destination</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="Delivery address..."
                  value={deliveryAddress}
                  onChange={e => setDeliveryAddress(e.target.value)}
                  style={{ fontSize: 'var(--text-sm)' }}
                />
              </div>

              {submitError && (
                <div style={{ color: '#c5221f', fontSize: 'var(--text-xs)', marginBottom: 'var(--sp-3)' }}>
                  {submitError}
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', padding: 'var(--sp-3)' }}
                disabled={submitting || orderLines.length === 0 || hasErrors}
              >
                {submitting ? 'Submitting Purchase Order...' : 'Submit Purchase Order →'}
              </button>
            </form>
          </div>
        </aside>
      </div>
    </div>
  );
}
