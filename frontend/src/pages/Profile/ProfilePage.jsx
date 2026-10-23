import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { updateProfile, getDealerProfile, updateDealerProfile, ApiError } from '../../api/client';
import { ErrorMessage, SuccessMessage, PageLoader } from '../../components/UI';
import '../Bakeries/Bakeries.css';
import './Profile.css';

export default function ProfilePage() {
  const { user } = useAuth();

  const [profileForm, setProfileForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
  });

  const [dealerForm, setDealerForm] = useState({
    business_name: '',
    contact_name: '',
    phone: '',
    delivery_address: '',
  });

  const [loading, setLoading] = useState(true);
  const [profileSaving, setProfileSaving] = useState(false);
  const [dealerSaving, setDealerSaving] = useState(false);

  const [profileSuccess, setProfileSuccess] = useState('');
  const [dealerSuccess, setDealerSuccess] = useState('');
  const [profileError, setProfileError] = useState(null);
  const [dealerError, setDealerError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      if (!user) return;
      setProfileForm({
        first_name: user.first_name ?? '',
        last_name: user.last_name ?? '',
        email: user.email ?? '',
      });

      try {
        const dRes = await getDealerProfile();
        if (isMounted && dRes?.dealer) {
          setDealerForm({
            business_name: dRes.dealer.business_name || '',
            contact_name: dRes.dealer.contact_name || '',
            phone: dRes.dealer.phone || '',
            delivery_address: dRes.dealer.delivery_address || '',
          });
        }
      } catch {
        // Dealer profile error
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadData();
    return () => { isMounted = false; };
  }, [user]);

  if (!user) {
    return (
      <div className="page-content">
        <div className="container" style={{ textAlign: 'center', paddingBlock: 'var(--sp-12)' }}>
          <p>Please log in to manage your account.</p>
          <Link to="/login" className="btn btn-primary" style={{ marginTop: 'var(--sp-4)' }}>
            Log in
          </Link>
        </div>
      </div>
    );
  }

  if (loading) return <PageLoader />;

  async function handleProfileSubmit(e) {
    e.preventDefault();
    setProfileSaving(true);
    setProfileError(null);
    setProfileSuccess('');
    try {
      await updateProfile(profileForm);
      setProfileSuccess('Account information updated successfully!');
      setTimeout(() => setProfileSuccess(''), 4000);
    } catch (err) {
      setProfileError(err instanceof ApiError ? err.message : 'Failed to update profile.');
    } finally {
      setProfileSaving(false);
    }
  }

  async function handleDealerSubmit(e) {
    e.preventDefault();
    setDealerSaving(true);
    setDealerError(null);
    setDealerSuccess('');
    try {
      await updateDealerProfile(dealerForm);
      setDealerSuccess('Commercial dealer details updated successfully!');
      setTimeout(() => setDealerSuccess(''), 4000);
    } catch (err) {
      setDealerError(err instanceof ApiError ? err.message : 'Failed to update dealer details.');
    } finally {
      setDealerSaving(false);
    }
  }

  return (
    <div className="page-content">
      <div className="container">
        {/* Header */}
        <div className="profile-header">
          <div>
            <span className="b2b-badge b2b-badge--primary" style={{ marginBottom: 'var(--sp-1)' }}>
              {user.role === 'seller' ? 'Dealer (Supplier)' : user.role === 'admin' ? 'Platform Admin' : 'Bakery Owner (Buyer)'}
            </span>
            <h1 className="heading-section">Account & Commercial Profile</h1>
            <p className="text-muted" style={{ marginTop: 'var(--sp-1)', fontSize: 'var(--text-sm)' }}>
              Manage commercial identity, wholesale contact details, and default delivery destinations.
            </p>
          </div>
        </div>

        <div className="profile-grid">
          {/* Commercial Bakery Profile (For Bakery Owners who purchase from Dealers) */}
          {user.role !== 'seller' && (
            <div className="profile-card">
              <h2 className="heading-section" style={{ fontSize: 'var(--text-lg)', borderBottom: '1px solid var(--border)', paddingBottom: 'var(--sp-3)', marginBottom: 'var(--sp-4)' }}>
                🥖 Bakery Commercial Business & Delivery Info
              </h2>

              {dealerSuccess && <SuccessMessage message={dealerSuccess} />}
              {dealerError && <ErrorMessage message={dealerError} />}

              <form onSubmit={handleDealerSubmit} className="profile-form">
                <div className="form-group">
                  <label className="form-label" htmlFor="dealer-biz-name">Business / Retailer Name</label>
                  <input
                    id="dealer-biz-name"
                    type="text"
                    className="form-input"
                    placeholder="e.g. Cornerstone Cafe & Bistro, Downtown Grocers..."
                    value={dealerForm.business_name}
                    onChange={e => setDealerForm({ ...dealerForm, business_name: e.target.value })}
                    disabled={dealerSaving}
                  />
                </div>

                <div className="form-row">
                  <div className="form-group flex-1">
                    <label className="form-label" htmlFor="dealer-contact-name">Order Contact Person</label>
                    <input
                      id="dealer-contact-name"
                      type="text"
                      className="form-input"
                      placeholder="e.g. Claire Cafe"
                      value={dealerForm.contact_name}
                      onChange={e => setDealerForm({ ...dealerForm, contact_name: e.target.value })}
                      disabled={dealerSaving}
                    />
                  </div>
                  <div className="form-group flex-1">
                    <label className="form-label" htmlFor="dealer-phone">Direct Phone</label>
                    <input
                      id="dealer-phone"
                      type="text"
                      className="form-input"
                      placeholder="+44 20..."
                      value={dealerForm.phone}
                      onChange={e => setDealerForm({ ...dealerForm, phone: e.target.value })}
                      disabled={dealerSaving}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="dealer-address">Default Commercial Delivery Address</label>
                  <textarea
                    id="dealer-address"
                    rows="3"
                    className="form-input"
                    placeholder="Full street address, delivery bay / entrance notes..."
                    value={dealerForm.delivery_address}
                    onChange={e => setDealerForm({ ...dealerForm, delivery_address: e.target.value })}
                    disabled={dealerSaving}
                  />
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  id="dealer-save-btn"
                  disabled={dealerSaving}
                >
                  {dealerSaving ? 'Saving...' : 'Save Commercial Information'}
                </button>
              </form>
            </div>
          )}

          {/* User Account Details */}
          <div className="profile-card">
            <h2 className="heading-section" style={{ fontSize: 'var(--text-lg)', borderBottom: '1px solid var(--border)', paddingBottom: 'var(--sp-3)', marginBottom: 'var(--sp-4)' }}>
              👤 User Account Information
            </h2>

            {profileSuccess && <SuccessMessage message={profileSuccess} />}
            {profileError && <ErrorMessage message={profileError} />}

            <form onSubmit={handleProfileSubmit} className="profile-form">
              <div className="form-group">
                <label className="form-label" htmlFor="prof-username">Username</label>
                <input
                  id="prof-username"
                  type="text"
                  className="form-input"
                  value={user.username}
                  disabled
                  readOnly
                />
              </div>

              <div className="form-row">
                <div className="form-group flex-1">
                  <label className="form-label" htmlFor="prof-first-name">First name</label>
                  <input
                    id="prof-first-name"
                    type="text"
                    className="form-input"
                    value={profileForm.first_name}
                    onChange={e => setProfileForm(f => ({ ...f, first_name: e.target.value }))}
                    disabled={profileSaving}
                  />
                </div>
                <div className="form-group flex-1">
                  <label className="form-label" htmlFor="prof-last-name">Last name</label>
                  <input
                    id="prof-last-name"
                    type="text"
                    className="form-input"
                    value={profileForm.last_name}
                    onChange={e => setProfileForm(f => ({ ...f, last_name: e.target.value }))}
                    disabled={profileSaving}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="prof-email">Email</label>
                <input
                  id="prof-email"
                  type="email"
                  className="form-input"
                  value={profileForm.email}
                  onChange={e => setProfileForm(f => ({ ...f, email: e.target.value }))}
                  disabled={profileSaving}
                />
              </div>

              <button
                type="submit"
                className="btn btn-secondary"
                id="prof-save-btn"
                disabled={profileSaving}
              >
                {profileSaving ? 'Saving...' : 'Save Account Info'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
