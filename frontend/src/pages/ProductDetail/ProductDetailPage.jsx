import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getProduct } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useCart } from '../../context/CartContext';
import { Spinner, ErrorMessage, PageLoader, SuccessMessage } from '../../components/UI';
import './ProductDetail.css';

const BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export default function ProductDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const { addToCart } = useCart();

  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  useEffect(() => {
    let isMounted = true;
    async function loadProduct() {
      setLoading(true);
      setError(null);
      try {
        const data = await getProduct(id);
        if (isMounted) {
          setProduct(data.product);
          setQuantity(1);
        }
      } catch (err) {
        if (isMounted) setError(err.message ?? 'Product not found.');
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadProduct();
    return () => { isMounted = false; };
  }, [id]);

  if (loading) return <PageLoader />;

  if (error || !product) {
    return (
      <div className="container" style={{ paddingBlock: 'var(--sp-12)' }}>
        <ErrorMessage
          message={error ?? 'Product not found.'}
          onRetry={() => window.location.reload()}
        />
        <div style={{ marginTop: 'var(--sp-6)' }}>
          <Link to="/shop" className="btn btn-secondary">← Back to Shop</Link>
        </div>
      </div>
    );
  }

  const imgSrc = product.image
    ? `${BASE}${product.image.startsWith('/') ? '' : '/'}${product.image}`
    : null;

  const isOutOfStock = product.quantity === 0;
  const isLowStock = product.quantity > 0 && product.quantity <= 5;

  async function handleAddToCart() {
    if (!user || isOutOfStock || adding) return;
    setAdding(true);
    setSuccessMsg('');
    try {
      await addToCart(product.id, quantity);
      setSuccessMsg(`Added ${quantity} ${product.title} to your cart!`);
      setTimeout(() => setSuccessMsg(''), 4000);
    } catch (err) {
      setError(err.message ?? 'Failed to add item to cart.');
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="page-content">
      <div className="container">
        {/* Breadcrumb */}
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <Link to="/">Home</Link>
          <span aria-hidden="true">/</span>
          <Link to="/shop">Shop</Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page">{product.title}</span>
        </nav>

        {successMsg && <SuccessMessage message={successMsg} />}

        <div className="product-detail">
          {/* Media gallery */}
          <div className="product-detail__media">
            {imgSrc ? (
              <img
                src={imgSrc}
                alt={product.title}
                className="product-detail__img"
              />
            ) : (
              <div className="product-detail__img-fallback" aria-hidden="true">
                🍰
              </div>
            )}
          </div>

          {/* Details & Actions */}
          <div className="product-detail__info">
            {product.category_label && (
              <span className="badge badge-accent" style={{ marginBottom: 'var(--sp-3)' }}>
                {product.category_label}
              </span>
            )}

            <h1 className="product-detail__title">{product.title}</h1>

            {product.seller_username && (
              <p className="product-detail__seller">
                Baked by <strong>{product.seller_username}</strong>
              </p>
            )}

            <div className="product-detail__price-row">
              <span className="product-detail__price">
                €{Number(product.price).toFixed(2)}
              </span>

              <span
                className={`stock-pill ${
                  isOutOfStock
                    ? 'stock-pill--out'
                    : isLowStock
                    ? 'stock-pill--low'
                    : 'stock-pill--in'
                }`}
              >
                {isOutOfStock
                  ? 'Out of stock'
                  : isLowStock
                  ? `Only ${product.quantity} left in stock`
                  : `${product.quantity} available`}
              </span>
            </div>

            {product.description && (
              <div className="product-detail__desc">
                <h3>About this bake</h3>
                <p>{product.description}</p>
              </div>
            )}

            {/* Cart controls */}
            <div className="product-detail__action-box">
              {user ? (
                <>
                  {!isOutOfStock && (
                    <div className="quantity-selector">
                      <label htmlFor="detail-qty" className="form-label" style={{ marginBottom: 0 }}>
                        Quantity:
                      </label>
                      <div className="quantity-controls">
                        <button
                          type="button"
                          className="btn-qty"
                          onClick={() => setQuantity(q => Math.max(1, q - 1))}
                          disabled={quantity <= 1 || adding}
                          aria-label="Decrease quantity"
                        >
                          −
                        </button>
                        <span className="quantity-value" id="detail-qty" aria-live="polite">
                          {quantity}
                        </span>
                        <button
                          type="button"
                          className="btn-qty"
                          onClick={() => setQuantity(q => Math.min(product.quantity, q + 1))}
                          disabled={quantity >= product.quantity || adding}
                          aria-label="Increase quantity"
                        >
                          +
                        </button>
                      </div>
                    </div>
                  )}

                  <button
                    id="product-detail-add-btn"
                    className="btn btn-primary btn-lg product-detail__submit-btn"
                    onClick={handleAddToCart}
                    disabled={isOutOfStock || adding}
                  >
                    {adding ? (
                      <><Spinner size={18} /> Adding…</>
                    ) : isOutOfStock ? (
                      'Out of Stock'
                    ) : (
                      `Add ${quantity > 1 ? `${quantity} items` : 'to Cart'} • €${(
                        Number(product.price) * quantity
                      ).toFixed(2)}`
                    )}
                  </button>
                </>
              ) : (
                <div className="product-detail__login-prompt">
                  <p>Please log in to add this item to your cart and place an order.</p>
                  <Link to="/login" className="btn btn-primary" id="detail-login-btn">
                    Log in to order
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
