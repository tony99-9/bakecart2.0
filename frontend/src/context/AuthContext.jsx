/**
 * AuthContext — session-based authentication state for BakeCart 2.0.
 *
 * State managed here:
 *   user   — null when logged out, UserProfile object when authenticated.
 *   loading — true during the initial profile check on app mount.
 *
 * On mount:
 *   1. Calls GET /api/auth/csrf/ to populate the CSRF cookie.
 *   2. Calls GET /api/auth/profile/ to restore session from HttpOnly cookie.
 *      If the response is 401 or 403 the user is unauthenticated (user=null).
 *
 * UserProfile shape (from backend users/api_views.py):
 *   { id, username, first_name, last_name, email, role, date_joined }
 *
 * role values from backend:
 *   'buyer' | 'seller' | 'admin'
 */

import { createContext, useContext, useEffect, useState } from 'react';
import { fetchCsrfCookie, getProfile, login as apiLogin, logout as apiLogout, ApiError } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function bootstrap() {
      try {
        // 1. Seed the CSRF cookie so subsequent POSTs are accepted.
        await fetchCsrfCookie();
        // 2. Restore session if an HttpOnly session cookie is present.
        const data = await getProfile();
        setUser(data.user);
      } catch (err) {
        // 401 / 403 → not logged in, that is fine.
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          setUser(null);
        } else {
          // Network / server error — stay unauthenticated, don't throw.
          console.warn('[auth] Could not restore session:', err.message);
          setUser(null);
        }
      } finally {
        setLoading(false);
      }
    }
    bootstrap();
  }, []);

  async function login(credentials) {
    const data = await apiLogin(credentials);
    setUser(data.user);
    return data.user;
  }

  async function logout() {
    try {
      await apiLogout();
    } catch (err) {
      console.warn('[auth] Server logout failed or session already cleared:', err);
    } finally {
      setUser(null);
      fetchCsrfCookie().catch(() => {});
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
