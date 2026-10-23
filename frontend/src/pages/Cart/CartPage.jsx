import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useCart } from '../../context/CartContext';
import { Spinner, ErrorMessage, EmptyState, PageLoader } from '../../components/UI';
import './Cart.css';

export default function CartPage() {
  const { user } = useAuth();
  const { cart, cartLoading, cartError, updateItem, removeItem, clearCart } = useCart();
  const navigate = useNavigate();

  const [mutatingId, setMutatingId] = useState(null);
  const [clearing, setClearing] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  if (!user) {
    return (
      <div className="page-content">
        <div className="container">
          <EmptyState
            icon="🔒"
            title="Sign in to view your cart"
            description="Your cart is tied to your account so you can continue where you left off."
            action={<Link to="/login" className="btn btn-primary">Log in</Link>}
          />
        </div>
      </div>
    );
  }

  if (cartLoading && !cart) {
    return <PageLoader />;
  }

  async function handleQtyChange(item, nextQty) {
    if (nextQty < 1 || mutatingId) return;
    setMutatingId(item.id);
    try {
      await updateItem(item.id, nextQty);
    } catch {
      // CartContext surfaces error
    } finally {
      setMutatingId(null);
    }
  }

  async function handleRemove(itemId) {
    if (mutatingId) return;
    setMutatingId(itemId);
    try {
      await removeItem(itemId);
    } catch {
      // CartContext surfaces error
    } finally {
      setMutatingId(null);
    }
  }

  async function handleClearCart() {
    setClearing(true);
    try {
      await clearCart();
      setShowClearConfirm(false);
    } catch {
      // error handled in context
    } finally {
      setClearing(false);
    }
  }

  const items = cart?.items ?? [];
  const isEmpty = items.length === 0;

  return (
    <div className="page-content">
      <div className="container">
        <div className="cart-header">
          <h1 className="heading-section">Your Shopping Cart</h1>
          {!isEmpty && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setShowClearConfirm(true)}
              disabled={clearing}
            >
              Clear Cart
            </button>
          )}
        </div>

        {cartError && <ErrorMessage message={cartError} />}

        {isEmpty ? (
          <EmptyState
            icon="🧺"
            title="Your cart is empty"
            description="Looks like you haven't added any delicious bakes to your cart yet."
            action={<Link to="/shop" className="btn btn-primary">Browse Bakery</Link>}
          />
        ) : (
          <div className="cart-grid">
            {/* Cart Items List */}
            <div className="cart-items">
              <div className="cart-items__header" aria-hidden="true">
                <span>Product</span>
                <span>Unit Price</span>
                <span>Quantity</span>
                <span>Total</span>
                <span></span>
              </div>

              {items.map(item => {
                const isMutating = mutatingId === item.id;
                return (
                  <div key={item.id} className="cart-item">
                    <div className="cart-item__title-col">
                      <Link to={`/products/${item.product_id}`} className="cart-item__name">
                        {item.product_title}
                      </Link>
                    </div>

                    <div className="cart-item__unit-price">
                      €{Number(item.unit_price).toFixed(2)}
                    </div>

                    <div className="cart-item__qty-controls">
                      <button
                        type="button"
                        className="btn-qty"
                        onClick={() => handleQtyChange(item, item.quantity - 1)}
                        disabled={item.quantity <= 1 || isMutating}
                        aria-label="Decrease quantity"
                      >
                        −
                      </button>
                      <span className="cart-item__qty-val" aria-live="polite">
                        {isMutating ? <Spinner size={12} /> : item.quantity}
                      </span>
                      <button
                        type="button"
                        className="btn-qty"
                        onClick={() => handleQtyChange(item, item.quantity + 1)}
                        disabled={isMutating}
                        aria-label="Increase quantity"
                      >
                        +
                      </button>
                    </div>

                    <div className="cart-item__line-total">
                      €{Number(item.line_total).toFixed(2)}
                    </div>

                    <div className="cart-item__actions">
                      <button
                        type="button"
                        className="cart-item__remove-btn"
                        onClick={() => handleRemove(item.id)}
                        disabled={isMutating}
                        aria-label={`Remove ${item.product_title} from cart`}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Cart Summary Card */}
            <aside className="cart-summary" aria-label="Order summary">
              <h2 className="cart-summary__title">Order Summary</h2>

              <div className="cart-summary__row">
                <span>Items ({items.reduce((acc, i) => acc + i.quantity, 0)})</span>
                <span>€{Number(cart.grand_total).toFixed(2)}</span>
              </div>

              <div className="cart-summary__row">
                <span>Shipping</span>
                <span className="cart-summary__free-shipping">Calculated at checkout</span>
              </div>

              <div className="cart-summary__divider" />

              <div className="cart-summary__total-row">
                <span>Total</span>
                <span>€{Number(cart.grand_total).toFixed(2)}</span>
              </div>

              <p className="cart-summary__note">
                Taxes included. Server-authoritative totals guaranteed at checkout.
              </p>

              <button
                id="cart-checkout-btn"
                className="btn btn-primary btn-lg cart-summary__checkout-btn"
                onClick={() => navigate('/checkout')}
              >
                Proceed to Checkout →
              </button>

              <Link to="/shop" className="cart-summary__continue-link">
                ← Continue Shopping
              </Link>
            </aside>
          </div>
        )}

        {/* Clear Confirmation Modal / Alert */}
        {showClearConfirm && (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="clear-modal-title">
            <div className="modal-card">
              <h3 id="clear-modal-title">Clear your shopping cart?</h3>
              <p>Are you sure you want to remove all items from your cart? This cannot be undone.</p>
              <div className="modal-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowClearConfirm(false)}
                  disabled={clearing}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleClearCart}
                  disabled={clearing}
                >
                  {clearing ? <><Spinner size={14} /> Clearing…</> : 'Yes, Clear Cart'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
