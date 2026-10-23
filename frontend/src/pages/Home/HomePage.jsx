import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getProducts } from '../../api/client';
import ProductCard from '../../components/ProductCard/ProductCard';
import { PageLoader, ErrorMessage } from '../../components/UI';
import './Home.css';

const CATEGORIES = [
  { name: 'Cakes', icon: '🎂', query: 'category=CA' },
  { name: 'Cupcakes', icon: '🧁', query: 'search=cupcake' },
  { name: 'Breads', icon: '🥖', query: 'search=bread' },
  { name: 'Cookies', icon: '🍪', query: 'category=CO' },
  { name: 'Pastries', icon: '🥐', query: 'search=pastry' },
  { name: 'Donuts', icon: '🍩', query: 'search=donut' },
  { name: 'Brownies', icon: '🍫', query: 'search=brownie' },
  { name: 'Pies', icon: '🥧', query: 'search=pie' },
  { name: 'Gift Hampers', icon: '🎁', query: 'search=hamper' },
  { name: 'View All', icon: '⊞', query: '' },
];

const VALUE_PROPS = [
  {
    icon: '🚚',
    title: 'Fast & Reliable Delivery',
    desc: 'Get fresh bakes at your doorstep',
  },
  {
    icon: '🛡️',
    title: 'Trusted Local Bakeries',
    desc: 'Quality you can count on',
  },
  {
    icon: '🍃',
    title: 'Fresh Ingredients',
    desc: 'Made with love and care',
  },
  {
    icon: '🎁',
    title: 'Perfect for Every Occasion',
    desc: 'Birthdays, weddings, or just because',
  },
];

const FEATURED_ORDER = [
  'Chocolate Truffle Cake',
  'Strawberry Fresh Cream',
  'Assorted Cupcakes (6 pcs)',
  'Sourdough Bread',
  'Chocolate Chip Cookies',
  'Red Velvet Cake',
];

export default function HomePage() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await getProducts({ page: 1 });
        const allItems = res.results || [];
        const sorted = [...allItems].sort((a, b) => {
          const indexA = FEATURED_ORDER.indexOf(a.title);
          const indexB = FEATURED_ORDER.indexOf(b.title);
          if (indexA !== -1 && indexB !== -1) return indexA - indexB;
          if (indexA !== -1) return -1;
          if (indexB !== -1) return 1;
          return 0;
        });
        setProducts(sorted);
      } catch (err) {
        setError(err.message || 'Could not load products.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="home-page">
      {/* ── 1. Hero Banner ─────────────────────────────────── */}
      <section className="hero-banner" aria-label="BakeCart Hero">
        <div className="container hero-banner__inner">
          <div className="hero-banner__content">
            <span className="hero-banner__eyebrow">
              FRESH BAKES, BRIGHTER DAYS
            </span>
            <h1 className="hero-banner__title">
              Delicious Cakes<br />for Every Moment
            </h1>
            <p className="hero-banner__subtitle">
              From everyday treats to special celebrations, find your favorite bakes from trusted local bakeries.
            </p>
            <div className="hero-banner__actions">
              <Link to="/shop" className="hero-banner__cta-btn" id="hero-shop-btn">
                Shop Now →
              </Link>
            </div>
          </div>

          <div className="hero-banner__media">
            <div className="hero-banner__img-wrapper">
              <img
                src="/hero_cake.jpg"
                alt="Delicious Celebration Chocolate Berry Cake"
                className="hero-banner__img"
                loading="eager"
              />
              <div className="hero-banner__badge" aria-hidden="true">
                <span className="hero-banner__badge-line">Made</span>
                <span className="hero-banner__badge-line">with Love</span>
                <span className="hero-banner__badge-heart">❤️</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── 2. Category Icons Strip ────────────────────────── */}
      <section className="category-strip-section" aria-label="Product Categories">
        <div className="container">
          <div className="category-strip">
            {CATEGORIES.map((cat) => {
              const toUrl = cat.query ? `/shop?${cat.query}` : '/shop';
              return (
                <Link key={cat.name} to={toUrl} className="category-item">
                  <div className="category-item__icon-bubble">
                    <span className="category-item__icon" aria-hidden="true">{cat.icon}</span>
                  </div>
                  <span className="category-item__name">{cat.name}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── 3. Featured Products Grid ──────────────────────── */}
      <section className="featured-section" aria-label="Featured Products">
        <div className="container">
          <div className="featured-header">
            <h2 className="featured-title">Featured Products</h2>
            <Link to="/shop" className="featured-view-all">
              View All →
            </Link>
          </div>

          {loading && <PageLoader />}
          {error && <ErrorMessage message={error} />}

          {!loading && !error && products.length === 0 && (
            <div className="featured-empty">
              <p>No products available at the moment.</p>
            </div>
          )}

          {!loading && !error && products.length > 0 && (
            <div className="featured-grid">
              {products.slice(0, 6).map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
          )}
        </div>
      </section>

      {/* ── 4. Value Proposition Strip ─────────────────────── */}
      <section className="value-props-section" aria-label="Our Guarantees">
        <div className="container">
          <div className="value-props-grid">
            {VALUE_PROPS.map((prop) => (
              <div key={prop.title} className="value-prop-card">
                <span className="value-prop-card__icon" aria-hidden="true">{prop.icon}</span>
                <div className="value-prop-card__content">
                  <h3 className="value-prop-card__title">{prop.title}</h3>
                  <p className="value-prop-card__desc">{prop.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
