import { NavLink, Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './Seller.css';

export default function SellerLayout({ children }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!user || (user.role !== 'seller' && user.role !== 'admin')) {
    return (
      <div className="page-content">
        <div className="container" style={{ textAlign: 'center', paddingBlock: 'var(--sp-12)' }}>
          <h2 className="heading-section">Seller Hub Access Required</h2>
          <p style={{ marginTop: 'var(--sp-2)', color: 'var(--clr-text-muted)' }}>
            This portal is restricted to registered bakery sellers.
          </p>
          <div style={{ marginTop: 'var(--sp-6)' }}>
            <Link to="/" className="btn btn-secondary">Return to Storefront</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-content">
      <div className="container">
        {/* Hub Header */}
        <div className="seller-hub-header">
          <div>
            <div className="seller-hub-badge">
              <span>📦 Dealer Supplier Portal</span>
            </div>
            <h1 className="heading-section" style={{ marginTop: 'var(--sp-2)' }}>
              Dealer Management Desk
            </h1>
            <p className="text-muted" style={{ fontSize: 'var(--text-sm)' }}>
              Manage your wholesale product catalogue, process incoming bakery purchase orders, and track deliveries.
            </p>
          </div>

          <Link to="/seller/products/new" className="btn btn-primary" id="seller-new-product-btn">
            + Add New Product
          </Link>
        </div>

        {/* Tab Navigation */}
        <nav className="seller-tabs" aria-label="Seller Hub Navigation">
          <NavLink
            to="/seller/overview"
            className={({ isActive }) => `seller-tab ${isActive ? 'seller-tab--active' : ''}`}
          >
            📊 Sales Summary
          </NavLink>
          <NavLink
            to="/seller/products"
            className={({ isActive }) =>
              `seller-tab ${isActive && location.pathname !== '/seller/products/new' ? 'seller-tab--active' : ''}`
            }
          >
            📦 Products & Stock
          </NavLink>
          <NavLink
            to="/seller/orders"
            className={({ isActive }) => `seller-tab ${isActive ? 'seller-tab--active' : ''}`}
          >
            📋 Bakery Orders
          </NavLink>
          <NavLink
            to="/seller/profile"
            className={({ isActive }) => `seller-tab ${isActive ? 'seller-tab--active' : ''}`}
          >
            🏢 Dealer Profile
          </NavLink>
        </nav>

        {/* Content body */}
        <div className="seller-content">
          {children ?? <Outlet />}
        </div>
      </div>
    </div>
  );
}
