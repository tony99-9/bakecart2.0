import { useState } from 'react';
import { NavLink, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useCart } from '../../context/CartContext';
import './Layout.css';

export default function Navbar() {
  const { user, logout } = useAuth();
  const { itemCount } = useCart();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

  function closeMenu() {
    setMobileOpen(false);
    setUserDropdownOpen(false);
  }

  function handleSearchSubmit(e) {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/shop?search=${encodeURIComponent(searchQuery.trim())}`);
      closeMenu();
    }
  }

  const roleLabel = user?.role === 'seller' ? 'Dealer' : user?.role === 'admin' ? 'Admin' : 'Bakery Owner';
  const displayName = user?.first_name || user?.username || 'Sarah';

  return (
    <nav className="navbar" role="navigation" aria-label="Main navigation">
      <div className="container navbar__inner">

        {/* Brand Logo */}
        <Link to="/" className="navbar__logo" onClick={closeMenu}>
          <span className="navbar__logo-icon" aria-hidden="true">🎂</span>
          <span className="navbar__logo-group">
            <span className="navbar__logo-text">BakeCart</span>
            <span className="navbar__logo-sub">Freshly Baked Happiness</span>
          </span>
        </Link>

        {/* Centered Search Bar */}
        <form className="navbar__search-form navbar__desktop-only" onSubmit={handleSearchSubmit}>
          <span className="navbar__search-icon" aria-hidden="true">🔍</span>
          <input
            type="search"
            className="navbar__search-input"
            placeholder="Search for cakes, breads, cookies..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search catalogue"
          />
        </form>

        {/* Desktop Nav links */}
        <ul className="navbar__links" role="list">
          <li><NavLink to="/" end>Home</NavLink></li>
          <li><NavLink to="/shop">Shop</NavLink></li>
          <li><NavLink to="/bakeries">Bakeries</NavLink></li>

          {user && user.role !== 'seller' && user.role !== 'admin' && (
            <li><NavLink to="/wholesale-order">Order Desk</NavLink></li>
          )}

          {user?.role === 'seller' && (
            <>
              <li><NavLink to="/seller/orders">Incoming</NavLink></li>
              <li><NavLink to="/seller/products">Products</NavLink></li>
            </>
          )}

          {user?.role === 'admin' && (
            <li><NavLink to="/admin/summary">Admin</NavLink></li>
          )}
        </ul>

        {/* Actions: Cart + User Profile */}
        <div className="navbar__actions">
          {/* Shopping Cart Icon with Badge */}
          <Link to="/cart" className="navbar__cart-btn" aria-label="Shopping Cart" onClick={closeMenu}>
            <span className="navbar__cart-icon" aria-hidden="true">🛒</span>
            <span className="navbar__cart-badge">{itemCount > 0 ? itemCount : 2}</span>
          </Link>

          {/* User Menu */}
          {user ? (
            <div className="navbar__user-container">
              <button
                type="button"
                className="navbar__user-btn"
                onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                aria-expanded={userDropdownOpen}
              >
                <span className="navbar__avatar" aria-hidden="true">👤</span>
                <span className="navbar__greeting">Hi, {displayName}</span>
                <span className="navbar__caret" aria-hidden="true">▾</span>
              </button>

              {userDropdownOpen && (
                <div className="navbar__dropdown-menu animate-fade-in">
                  <div className="navbar__dropdown-header">
                    <strong>{user.username}</strong>
                    <span className="b2b-badge b2b-badge--primary">{roleLabel}</span>
                  </div>
                  <hr className="navbar__dropdown-divider" />
                  <Link to="/profile" onClick={closeMenu} className="navbar__dropdown-item">Account Settings</Link>
                  <Link to="/orders" onClick={closeMenu} className="navbar__dropdown-item">My Orders</Link>
                  {user.role === 'seller' && (
                    <Link to="/seller/overview" onClick={closeMenu} className="navbar__dropdown-item">Dealer Dashboard</Link>
                  )}
                  {user.role === 'admin' && (
                    <Link to="/admin/summary" onClick={closeMenu} className="navbar__dropdown-item">Admin Dashboard</Link>
                  )}
                  <hr className="navbar__dropdown-divider" />
                  <button
                    className="navbar__dropdown-item navbar__dropdown-logout"
                    onClick={() => { closeMenu(); logout(); }}
                  >
                    Log out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="navbar__auth-links navbar__desktop-only">
              <Link to="/login" className="btn btn-ghost btn-sm" id="nav-login-btn">Log in</Link>
              <Link to="/register" className="btn btn-primary btn-sm" id="nav-register-btn">Sign up</Link>
            </div>
          )}

          {/* Mobile hamburger button */}
          <button
            className="navbar__mobile-toggle"
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen(prev => !prev)}
          >
            {mobileOpen ? '✕' : '☰'}
          </button>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {mobileOpen && (
        <div className="navbar__mobile-menu animate-fade-in" role="dialog" aria-modal="false">
          <form className="navbar__mobile-search" onSubmit={handleSearchSubmit}>
            <input
              type="search"
              placeholder="Search for cakes, breads, cookies..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button type="submit" className="btn btn-primary btn-sm">Search</button>
          </form>

          <ul className="navbar__mobile-links" role="list">
            <li><NavLink to="/" end onClick={closeMenu}>Home</NavLink></li>
            <li><NavLink to="/shop" onClick={closeMenu}>Shop</NavLink></li>
            <li><NavLink to="/bakeries" onClick={closeMenu}>Bakeries</NavLink></li>

            {user && user.role !== 'seller' && user.role !== 'admin' && (
              <>
                <li><NavLink to="/wholesale-order" onClick={closeMenu}>Bakery Order Desk</NavLink></li>
                <li><NavLink to="/orders" onClick={closeMenu}>My Purchase Orders</NavLink></li>
              </>
            )}

            {user?.role === 'seller' && (
              <>
                <li><NavLink to="/seller/orders" onClick={closeMenu}>Incoming Orders</NavLink></li>
                <li><NavLink to="/seller/products" onClick={closeMenu}>Products & Stock</NavLink></li>
                <li><NavLink to="/seller/overview" onClick={closeMenu}>Sales</NavLink></li>
              </>
            )}

            {user?.role === 'admin' && (
              <>
                <li><NavLink to="/admin/summary" onClick={closeMenu}>Overview</NavLink></li>
                <li><NavLink to="/admin/users" onClick={closeMenu}>Users & Roles</NavLink></li>
                <li><NavLink to="/admin/products" onClick={closeMenu}>All Catalogues</NavLink></li>
              </>
            )}

            {user ? (
              <>
                <li><NavLink to="/profile" onClick={closeMenu}>Account Settings</NavLink></li>
                <li>
                  <button className="btn btn-ghost btn-sm" onClick={() => { closeMenu(); logout(); }}>
                    Log out
                  </button>
                </li>
              </>
            ) : (
              <>
                <li><NavLink to="/login" onClick={closeMenu}>Log in</NavLink></li>
                <li><NavLink to="/register" onClick={closeMenu}>Sign up</NavLink></li>
              </>
            )}
          </ul>
        </div>
      )}
    </nav>
  );
}
