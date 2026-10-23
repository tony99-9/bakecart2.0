import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getB2BBakeryCatalogue, createB2BOrder, authorizeB2BBakery } from '../../api/client';
import { PageLoader, ErrorMessage, EmptyState } from '../../components/UI';
import { useAuth } from '../../context/AuthContext';
import './Bakeries.css';

export default function BakeryCataloguePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [bakery, setBakery] = useState(null);
  const [products, setProducts] = useState([]);
  const [quantities, setQuantities] = useState({});
  const [notes, setNotes] = useState('');
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    loadCatalogue();
  }, [id]);

  useEffect(() => {
    if (user?.dealer_profile?.delivery_address) {
      setDeliveryAddress(user.dealer_profile.delivery_address);
    }
  }, [user]);

  async function loadCatalogue() {
    setLoading(true);
    setError(null);
    try {
      const res = await getB2BBakeryCatalogue(id);
      setBakery(res.bakery);
      setProducts(res.products || []);
      // Initialize quantities to 0
      const initQ = {};
      (res.products || []).forEach(p => { initQ[p.id] = 0; });
      setQuantities(initQ);
    } catch (err) {
      setError(err.message || 'Could not load bakery catalogue.');
    } finally {
      setLoading(false);
    }
  }

  function handleQuantityChange(productId, val) {
    const num = Math.max(0, parseInt(val, 10) || 0);
    setQuantities(prev => ({ ...prev, [productId]: num }));
  }

  function handleSetMOQ(product) {
    setQuantities(prev => ({ ...prev, [product.id]: product.min_order_quantity }));
  }

  // Calculate items in draft
  const orderItems = products
    .filter(p => (quantities[p.id] || 0) > 0)
    .map(p => ({
      product: p,
      quantity: quantities[p.id],
      subtotal: (parseFloat(p.price) * quantities[p.id]).toFixed(2),
      isUnderMOQ: quantities[p.id] < p.min_order_quantity,
      isOverStock: quantities[p.id] > p.quantity,
    }));

  const orderTotal = orderItems.reduce((acc, item) => acc + parseFloat(item.subtotal), 0).toFixed(2);
  const hasValidationErrors = orderItems.some(item => item.isUnderMOQ || item.isOverStock);

  async function handleSubmitOrder(e) {
    e.preventDefault();
    if (!user) {
      navigate('/login');
      return;
    }
    if (orderItems.length === 0) {
      setSubmitError('Please specify quantities for at least one product.');
      return;
    }
    if (hasValidationErrors) {
      setSubmitError('Please resolve minimum order quantities and stock warnings before submitting.');
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    const payload = {
      bakery_id: parseInt(id, 10),
      items: orderItems.map(item => ({
        product_id: item.product.id,
        quantity: item.quantity,
      })),
      notes,
      delivery_address: deliveryAddress,
    };

    try {
      const res = await createB2BOrder(payload);
      navigate(`/orders/${res.order.id}`, {
        state: { flashMessage: 'Wholesale order submitted! Awaiting dealer confirmation.' }
      });
    } catch (err) {
      setSubmitError(err.message || 'Failed to submit wholesale order.');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <PageLoader />;
  if (error) return <div className="container" style={{ padding: 'var(--sp-8) 0' }}><ErrorMessage message={error} onRetry={loadCatalogue} /></div>;
  if (!bakery) return null;

  return (
    <div className="container" style={{ padding: 'var(--sp-8) 0' }}>
      {/* Supplier Header */}
      <div style={{ background: 'var(--surface)', padding: 'var(--sp-6)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)', marginBottom: 'var(--sp-8)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--sp-4)' }}>
          <div>
            <Link to="/bakeries" style={{ fontSize: 'var(--text-sm)', color: 'var(--primary)', fontWeight: 600 }}>
              ← All Dealers & Suppliers
            </Link>
            <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 800, margin: 'var(--sp-2) 0' }}>
              {bakery.name}
            </h1>
            <p style={{ color: 'var(--text-muted)', maxWidth: '640px' }}>
              {bakery.description || 'Wholesale supplier of products and ingredients for commercial bakeries.'}
            </p>
          </div>
          <div>
            {bakery.is_authorized ? (
              <span className="b2b-badge b2b-badge--success">✓ Authorized Bakery Customer</span>
            ) : (
              <button
                className="btn btn-primary btn-sm"
                onClick={async () => {
                  try {
                    await authorizeB2BBakery(bakery.id);
                    await loadCatalogue();
                  } catch (e) {
                    alert(e.message);
                  }
                }}
              >
                Request Authorization
              </button>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-6)', marginTop: 'var(--sp-4)', paddingTop: 'var(--sp-4)', borderTop: '1px solid var(--border)', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
          {bakery.address && <div><strong>Location:</strong> {bakery.address}</div>}
          {bakery.phone && <div><strong>Phone:</strong> {bakery.phone}</div>}
          {bakery.email && <div><strong>Email:</strong> {bakery.email}</div>}
        </div>
      </div>

      {/* Catalogue & Order Sheet Layout */}
      <div className="catalogue-layout">
        {/* Products List */}
        <div>
          <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, marginBottom: 'var(--sp-4)' }}>
            Wholesale Product Catalogue ({products.length})
          </h2>

          {products.length === 0 ? (
            <EmptyState icon="🥐" title="No Products Available" message="This bakery currently has no active products in their wholesale catalogue." />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
              {products.map(product => {
                const qty = quantities[product.id] || 0;
                const isUnderMOQ = qty > 0 && qty < product.min_order_quantity;
                const isOverStock = qty > product.quantity;

                return (
                  <div
                    key={product.id}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '100px 1fr 140px 140px',
                      gap: 'var(--sp-4)',
                      background: 'var(--surface)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-md)',
                      padding: 'var(--sp-4)',
                      alignItems: 'center',
                    }}
                  >
                    <img
                      src={product.image || '/placeholder-bakery.png'}
                      alt={product.title}
                      style={{ width: '100px', height: '80px', objectFit: 'cover', borderRadius: 'var(--radius-sm)' }}
                      onError={e => { e.currentTarget.style.display = 'none'; }}
                    />

                    <div>
                      <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 700, margin: 0 }}>
                        {product.title}
                      </h3>
                      <div style={{ display: 'flex', gap: 'var(--sp-2)', marginTop: '4px', flexWrap: 'wrap' }}>
                        <span className="b2b-badge b2b-badge--primary">{product.category_label || 'Bakery'}</span>
                        <span className="b2b-badge b2b-badge--info">Unit: {product.unit}</span>
                        <span className="b2b-badge b2b-badge--warning">MOQ: {product.min_order_quantity}</span>
                      </div>
                      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginTop: '4px' }}>
                        In stock: <strong>{product.quantity}</strong> {product.unit}s
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--primary-dark)' }}>
                        €{product.price}
                      </div>
                      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                        per {product.unit}
                      </div>
                    </div>

                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-1)' }}>
                        <input
                          type="number"
                          className="form-control"
                          min="0"
                          max={product.quantity}
                          value={qty}
                          onChange={e => handleQuantityChange(product.id, e.target.value)}
                          style={{ width: '80px', textAlign: 'center' }}
                        />
                        {qty === 0 && (
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            style={{ fontSize: 'var(--text-xs)', padding: '4px 6px' }}
                            onClick={() => handleSetMOQ(product)}
                            title="Set to Minimum Order Quantity"
                          >
                            +MOQ
                          </button>
                        )}
                      </div>
                      {isUnderMOQ && (
                        <div style={{ color: 'var(--color-danger, #c5221f)', fontSize: '11px', marginTop: '2px' }}>
                          Min {product.min_order_quantity} required
                        </div>
                      )}
                      {isOverStock && (
                        <div style={{ color: 'var(--color-danger, #c5221f)', fontSize: '11px', marginTop: '2px' }}>
                          Max {product.quantity} available
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Order Sheet Sidebar */}
        <aside>
          <div className="order-sheet-card">
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, marginBottom: 'var(--sp-4)', borderBottom: '1px solid var(--border)', paddingBottom: 'var(--sp-2)' }}>
              Purchase Order Sheet
            </h3>

            {orderItems.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
                Select quantities for the products you wish to order from {bakery.name}.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
                {orderItems.map(item => (
                  <div key={item.product.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)' }}>
                    <span>
                      {item.quantity} × {item.product.title}
                    </span>
                    <strong style={{ marginLeft: 'var(--sp-2)' }}>€{item.subtotal}</strong>
                  </div>
                ))}
                <div style={{ borderTop: '1px dashed var(--border)', paddingTop: 'var(--sp-3)', display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-lg)', fontWeight: 800 }}>
                  <span>Wholesale Total</span>
                  <span style={{ color: 'var(--primary-dark)' }}>€{orderTotal}</span>
                </div>
              </div>
            )}

            <form onSubmit={handleSubmitOrder} style={{ marginTop: 'var(--sp-4)' }}>
              <div className="form-group" style={{ marginBottom: 'var(--sp-3)' }}>
                <label className="form-label" style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>
                  Delivery Instructions / Notes
                </label>
                <textarea
                  className="form-control"
                  rows="2"
                  placeholder="e.g. Deliver to loading dock before 7am..."
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  style={{ fontSize: 'var(--text-sm)' }}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 'var(--sp-4)' }}>
                <label className="form-label" style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>
                  Delivery Address
                </label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="Destination commercial address..."
                  value={deliveryAddress}
                  onChange={e => setDeliveryAddress(e.target.value)}
                  style={{ fontSize: 'var(--text-sm)' }}
                />
              </div>

              {submitError && (
                <div style={{ color: 'var(--color-danger, #c5221f)', fontSize: 'var(--text-xs)', marginBottom: 'var(--sp-3)' }}>
                  {submitError}
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', padding: 'var(--sp-3)' }}
                disabled={submitting || orderItems.length === 0 || hasValidationErrors}
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
