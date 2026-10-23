import { NavLink, Link, Outlet } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './Admin.css';

export default function AdminLayout({ children }) {
  const { user } = useAuth();

  if (!user || user.role !== 'admin') {
    return (
      <div className="page-content">
        <div className="container" style={{ textAlign: 'center', paddingBlock: 'var(--sp-12)' }}>
          <h2 className="heading-section">Administrator Access Required</h2>
          <p style={{ marginTop: 'var(--sp-2)', color: 'var(--clr-text-muted)' }}>
            This portal is restricted to authorized marketplace administrators.
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
        {/* Admin Header */}
        <div className="admin-header">
          <div>
            <div className="admin-badge">
              <span>🛡️ Platform Administration</span>
            </div>
            <h1 className="heading-section" style={{ marginTop: 'var(--sp-2)' }}>
              Marketplace Oversight
            </h1>
            <p className="text-muted" style={{ fontSize: 'var(--text-sm)' }}>
              Comprehensive governance over users, seller accounts, products, orders, and sales metrics.
            </p>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav className="admin-tabs" aria-label="Admin Navigation">
          <NavLink
            to="/admin/summary"
            className={({ isActive }) => `admin-tab ${isActive ? 'admin-tab--active' : ''}`}
          >
            📊 Metrics & Overview
          </NavLink>
          <NavLink
            to="/admin/users"
            className={({ isActive }) => `admin-tab ${isActive ? 'admin-tab--active' : ''}`}
          >
            👥 User & Seller Management
          </NavLink>
          <NavLink
            to="/admin/products"
            className={({ isActive }) => `admin-tab ${isActive ? 'admin-tab--active' : ''}`}
          >
            🍰 Product Oversight
          </NavLink>
          <NavLink
            to="/admin/orders"
            className={({ isActive }) => `admin-tab ${isActive ? 'admin-tab--active' : ''}`}
          >
            📦 Order Oversight
          </NavLink>
        </nav>

        {/* Content */}
        <div className="admin-content">
          {children ?? <Outlet />}
        </div>
      </div>
    </div>
  );
}
