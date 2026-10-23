import { useState, useEffect } from 'react';
import { getBakeryProfile, updateBakeryProfile } from '../../api/client';
import { PageLoader, ErrorMessage } from '../../components/UI';
import SellerLayout from './SellerLayout';

export default function BakeryProfilePage() {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    address: '',
    phone: '',
    email: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    loadProfile();
  }, []);

  async function loadProfile() {
    setLoading(true);
    setError(null);
    try {
      const res = await getBakeryProfile();
      const b = res.bakery || {};
      setFormData({
        name: b.name || '',
        description: b.description || '',
        address: b.address || '',
        phone: b.phone || '',
        email: b.email || '',
      });
    } catch (err) {
      setError(err.message || 'Could not load bakery profile.');
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await updateBakeryProfile(formData);
      setSuccess('Bakery profile updated successfully.');
    } catch (err) {
      setError(err.message || 'Failed to update bakery profile.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <SellerLayout>
      <div className="data-table-card" style={{ maxWidth: '640px' }}>
        <div className="data-table-toolbar">
          <div>
            <h2 className="heading-section" style={{ fontSize: 'var(--text-lg)', margin: 0 }}>
              Bakery Business Profile
            </h2>
            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
              This commercial information is displayed to authorized dealers when browsing your catalogue.
            </p>
          </div>
        </div>

        <div style={{ padding: 'var(--sp-6)' }}>
          {error && <ErrorMessage message={error} />}
          {success && (
            <div style={{ background: '#e6f4ea', border: '1px solid #34a853', color: '#137333', padding: 'var(--sp-3)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--sp-4)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>
              ✓ {success}
            </div>
          )}

          {loading ? (
            <PageLoader />
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
              <div className="form-group">
                <label className="form-label" style={{ fontWeight: 600 }}>Bakery Business Name</label>
                <input
                  type="text"
                  className="form-control"
                  required
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label" style={{ fontWeight: 600 }}>Commercial Description</label>
                <textarea
                  className="form-control"
                  rows="3"
                  placeholder="e.g. Supplying certified organic sourdough and morning goods..."
                  value={formData.description}
                  onChange={e => setFormData({ ...formData, description: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label" style={{ fontWeight: 600 }}>Bakery / Dispatch Address</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="Facility or dispatch location address..."
                  value={formData.address}
                  onChange={e => setFormData({ ...formData, address: e.target.value })}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-4)' }}>
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Order Desk Phone</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="+44 20..."
                    value={formData.phone}
                    onChange={e => setFormData({ ...formData, phone: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Wholesale Inquiries Email</label>
                  <input
                    type="email"
                    className="form-control"
                    placeholder="orders@bakery.com"
                    value={formData.email}
                    onChange={e => setFormData({ ...formData, email: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ marginTop: 'var(--sp-2)' }}>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Saving Changes...' : 'Save Bakery Profile'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </SellerLayout>
  );
}
