import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useCart } from '../../context/CartContext';
import { getAddress, saveAddress, checkout, createPaymentIntent, ApiError } from '../../api/client';
import { Spinner, ErrorMessage, PageLoader } from '../../components/UI';
import './Checkout.css';

export default function CheckoutPage() {
  const { user } = useAuth();
  const { cart, cartLoading, loadCart } = useCart();
  const navigate = useNavigate();

  const [address, setAddress] = useState({
    street_name: '',
    house_number: '',
    city: '',
    country: '',
  });
  const [addressLoading, setAddressLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    async function fetchSavedAddress() {
      if (!user) return;
      try {
        const data = await getAddress();
        if (isMounted && data?.address) {
          setAddress({
            street_name: data.address.street_name ?? '',
            house_number: data.address.house_number ?? '',
            city: data.address.city ?? '',
            country: data.address.country ?? '',
          });
        }
      } catch {
        // No saved address or fetch error — keep blank form
      } finally {
        if (isMounted) setAddressLoading(false);
      }
    }
    fetchSavedAddress();
    return () => { isMounted = false; };
  }, [user]);

  if (!user) {
    return (
      <div className="page-content">
        <div className="container" style={{ textAlign: 'center', paddingBlock: 'var(--sp-12)' }}>
          <p>Please log in to proceed with checkout.</p>
          <Link to="/login" className="btn btn-primary" style={{ marginTop: 'var(--sp-4)' }}>
            Log in
          </Link>
        </div>
      </div>
    );
  }

  if (cartLoading || addressLoading) {
    return <PageLoader />;
  }

  const items = cart?.items ?? [];
  if (items.length === 0) {
    return (
      <div className="page-content">
        <div className="container" style={{ textAlign: 'center', paddingBlock: 'var(--sp-12)' }}>
          <h2 className="heading-section">Your cart is empty</h2>
          <p style={{ marginTop: 'var(--sp-2)', color: 'var(--clr-text-muted)' }}>
            Add items to your cart before proceeding to checkout.
          </p>
          <Link to="/shop" className="btn btn-primary" style={{ marginTop: 'var(--sp-6)' }}>
            Go to Shop
          </Link>
        </div>
      </div>
    );
  }

  function handleAddressChange(e) {
    setAddress(a => ({ ...a, [e.target.name]: e.target.value }));
  }

  async function handleCheckout(e) {
    e.preventDefault();
    if (submitting) return;

    if (!address.street_name || !address.house_number || !address.city || !address.country) {
      setError('Please complete all shipping address fields.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      // 1. Save or update the shipping address to get its ID
      const saved = await saveAddress(address);
      const addressId = saved?.address?.id;

      // 2. Perform atomic server-side checkout
      const checkoutRes = await checkout({ shipping_address_id: addressId });
      const createdOrder = checkoutRes.order;

      // 3. Initiate payment intent
      try {
        await createPaymentIntent(createdOrder.id);
      } catch (payErr) {
        console.warn('Payment intent creation deferred:', payErr.message);
      }

      // 4. Refresh cart state (it was cleared on the server)
      await loadCart();

      // 5. Navigate to order detail page
      navigate(`/orders/${createdOrder.id}`, {
        state: { justPlaced: true },
        replace: true,
      });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message ?? 'Checkout failed.');
      } else {
        setError('Checkout could not be completed. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-content">
      <div className="container">
        <h1 className="heading-section" style={{ marginBottom: 'var(--sp-8)' }}>
          Checkout
        </h1>

        {error && <ErrorMessage message={error} />}

        <div className="checkout-grid">
          {/* Left column: Shipping Address Form */}
          <div className="checkout-main">
            <div className="checkout-card">
              <h2 className="checkout-card__title">1. Shipping Address</h2>
              <form id="checkout-form" onSubmit={handleCheckout} className="checkout-form">
                <div className="form-row">
                  <div className="form-group flex-2">
                    <label className="form-label" htmlFor="street_name">Street Name</label>
                    <input
                      id="street_name"
                      name="street_name"
                      type="text"
                      className="form-input"
                      value={address.street_name}
                      onChange={handleAddressChange}
                      required
                      placeholder="e.g. Baker Street"
                      disabled={submitting}
                    />
                  </div>
                  <div className="form-group flex-1">
                    <label className="form-label" htmlFor="house_number">House/Apt #</label>
                    <input
                      id="house_number"
                      name="house_number"
                      type="text"
                      className="form-input"
                      value={address.house_number}
                      onChange={handleAddressChange}
                      required
                      placeholder="e.g. 221B"
                      disabled={submitting}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group flex-1">
                    <label className="form-label" htmlFor="city">City</label>
                    <input
                      id="city"
                      name="city"
                      type="text"
                      className="form-input"
                      value={address.city}
                      onChange={handleAddressChange}
                      required
                      placeholder="e.g. Dublin"
                      disabled={submitting}
                    />
                  </div>
                  <div className="form-group flex-1">
                    <label className="form-label" htmlFor="country">Country</label>
                    <input
                      id="country"
                      name="country"
                      type="text"
                      className="form-input"
                      value={address.country}
                      onChange={handleAddressChange}
                      required
                      placeholder="e.g. Ireland"
                      disabled={submitting}
                    />
                  </div>
                </div>
              </form>
            </div>

            <div className="checkout-card" style={{ marginTop: 'var(--sp-6)' }}>
              <h2 className="checkout-card__title">2. Payment Method</h2>
              <div className="payment-method-box">
                <span className="payment-method-badge">💳 Stripe Online Payment</span>
                <p className="text-muted" style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--sp-2)' }}>
                  A payment session will be generated securely via Stripe upon order confirmation.
                  No card details are stored on our servers.
                </p>
              </div>
            </div>
          </div>

          {/* Right column: Order Review */}
          <aside className="checkout-sidebar">
            <div className="checkout-card">
              <h2 className="checkout-card__title">Order Summary</h2>

              <div className="checkout-items">
                {items.map(item => (
                  <div key={item.id} className="checkout-item-row">
                    <div className="checkout-item-title">
                      <span>{item.product_title}</span>
                      <span className="checkout-item-qty">× {item.quantity}</span>
                    </div>
                    <span className="checkout-item-total">
                      €{Number(item.line_total).toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>

              <div className="checkout-divider" />

              <div className="checkout-summary-row">
                <span>Subtotal</span>
                <span>€{Number(cart.grand_total).toFixed(2)}</span>
              </div>
              <div className="checkout-summary-row">
                <span>Shipping</span>
                <span style={{ color: '#2e7d32', fontWeight: 600 }}>Free</span>
              </div>

              <div className="checkout-divider" />

              <div className="checkout-summary-total">
                <span>Total to pay</span>
                <span>€{Number(cart.grand_total).toFixed(2)}</span>
              </div>

              <button
                id="place-order-submit-btn"
                type="submit"
                form="checkout-form"
                className="btn btn-primary btn-lg"
                style={{ width: '100%', marginTop: 'var(--sp-6)' }}
                disabled={submitting}
              >
                {submitting ? (
                  <><Spinner size={18} /> Processing Order…</>
                ) : (
                  `Place Order • €${Number(cart.grand_total).toFixed(2)}`
                )}
              </button>

              <p className="checkout-security-note">
                🔒 256-bit encrypted checkout with server-authoritative stock deduction.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
