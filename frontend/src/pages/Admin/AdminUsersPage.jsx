import { useState, useEffect, useCallback, useRef } from 'react';
import { getAdminUsers, assignUserRole, ApiError } from '../../api/client';
import { PageLoader, ErrorMessage, Spinner, SuccessMessage } from '../../components/UI';
import AdminLayout from './AdminLayout';

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [updatingId, setUpdatingId] = useState(null);
  const [actionSuccess, setActionSuccess] = useState('');
  const [actionError, setActionError] = useState(null);
  const searchTimer = useRef(null);

  const load = useCallback(async (s, r) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminUsers({ search: s, role: r });
      setUsers(res.users ?? []);
    } catch (err) {
      setError(err.message ?? 'Could not load users list.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(search, roleFilter);
  }, [search, roleFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSearchChange(e) {
    const val = e.target.value;
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setSearch(val);
    }, 350);
  }

  async function handleRoleChange(userId, targetRole) {
    setUpdatingId(userId);
    setActionError(null);
    setActionSuccess('');
    try {
      await assignUserRole(userId, targetRole);
      setActionSuccess(`User #${userId} role updated to "${targetRole}".`);
      setTimeout(() => setActionSuccess(''), 4000);
      await load(search, roleFilter);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Failed to update user role.');
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <AdminLayout>
      <div className="data-table-card">
        {/* Filter Bar */}
        <div className="admin-filter-bar">
          <div className="shop-search" style={{ minWidth: '240px' }}>
            <span aria-hidden="true" style={{ color: 'var(--clr-text-subtle)' }}>🔍</span>
            <input
              type="search"
              placeholder="Search by username, name, email…"
              onChange={handleSearchChange}
              aria-label="Search users"
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
            <label htmlFor="role-select" style={{ fontSize: 'var(--text-sm)', color: 'var(--clr-text-muted)' }}>
              Filter Role:
            </label>
            <select
              id="role-select"
              className="admin-select"
              value={roleFilter}
              onChange={e => setRoleFilter(e.target.value)}
            >
              <option value="">All Roles</option>
              <option value="buyer">Buyers</option>
              <option value="seller">Sellers</option>
              <option value="admin">Admins</option>
            </select>
          </div>
        </div>

        {actionSuccess && <SuccessMessage message={actionSuccess} />}
        {actionError && <ErrorMessage message={actionError} />}
        {error && <ErrorMessage message={error} onRetry={() => load(search, roleFilter)} />}

        {loading ? (
          <PageLoader />
        ) : users.length === 0 ? (
          <div style={{ padding: 'var(--sp-12)', textAlign: 'center', color: 'var(--clr-text-muted)' }}>
            No accounts found matching your filters.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Full Name</th>
                  <th>Email</th>
                  <th>Current Role</th>
                  <th>Joined</th>
                  <th style={{ textAlign: 'right' }}>Role Governance</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => {
                  const isUpdating = updatingId === u.id;
                  const isAdmin = u.role === 'admin';
                  const dateStr = new Date(u.date_joined).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  });

                  return (
                    <tr key={u.id}>
                      <td>#{u.id}</td>

                      <td>
                        <strong>{u.username}</strong>
                      </td>

                      <td>
                        {u.first_name || u.last_name ? (
                          `${u.first_name} ${u.last_name}`.trim()
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>

                      <td>{u.email || <span className="text-muted">—</span>}</td>

                      <td>
                        <span
                          className={`badge ${
                            isAdmin
                              ? 'badge-accent'
                              : u.role === 'seller'
                              ? 'badge-active'
                              : ''
                          }`}
                          style={{
                            background: isAdmin ? '#e8eaf6' : u.role === 'seller' ? 'rgba(46, 125, 50, 0.12)' : 'var(--clr-surface-2)',
                            color: isAdmin ? '#283593' : u.role === 'seller' ? '#2e7d32' : 'var(--clr-text)',
                            textTransform: 'capitalize',
                          }}
                        >
                          {u.role}
                        </span>
                      </td>

                      <td style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-muted)' }}>
                        {dateStr}
                      </td>

                      <td style={{ textAlign: 'right' }}>
                        {isAdmin ? (
                          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-subtle)', fontStyle: 'italic' }}>
                            Django Staff
                          </span>
                        ) : u.role === 'seller' ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleRoleChange(u.id, 'buyer')}
                            disabled={isUpdating}
                          >
                            {isUpdating ? <Spinner size={12} /> : 'Revoke Seller Role'}
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={() => handleRoleChange(u.id, 'seller')}
                            disabled={isUpdating}
                          >
                            {isUpdating ? <Spinner size={12} /> : 'Grant Seller Role'}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
