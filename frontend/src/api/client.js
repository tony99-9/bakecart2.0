/**
 * Centralised API client for BakeCart 2.0.
 *
 * Strategy
 * ────────
 * Authentication: Django session + HttpOnly cookie.
 * CSRF: We call GET /api/auth/csrf/ once on app boot to obtain the CSRF
 *       cookie, then read it on every mutating request via getCsrfToken()
 *       and send it as the X-CSRFToken header. This matches the Django
 *       SessionAuthentication requirement documented in users/api_views.py.
 *
 * All requests use fetch() with credentials:'include' so the session cookie
 * and CSRF cookie are sent cross-origin (the backend has CORS_ALLOW_CREDENTIALS=True).
 *
 * No credentials, tokens, or user data are stored in localStorage.
 *
 * Error handling
 * ──────────────
 * On non-2xx responses the client parses the JSON body (which the Django
 * backend always returns) and throws an ApiError so callers get a typed
 * error with the backend's `error` string and optional `details` map.
 */

const BASE = import.meta.env.VITE_API_BASE_URL;

if (!BASE) {
  throw new Error(
    '[api] VITE_API_BASE_URL is not set. ' +
    'Copy .env.example to .env.local and set the backend URL.'
  );
}

// ─── CSRF ────────────────────────────────────────────────────────────────────

let inMemoryCsrfToken = '';

/** Read the csrftoken cookie or in-memory token. */
function getCsrfToken() {
  if (inMemoryCsrfToken) return inMemoryCsrfToken;
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

/**
 * Fetch the CSRF cookie and token from the backend.
 * Must be called once before the first mutating request.
 * Called automatically by the AuthProvider on app mount.
 */
export async function fetchCsrfCookie() {
  const res = await fetch(`${BASE}/api/auth/csrf/`, {
    method: 'GET',
    credentials: 'include',
  });
  const data = await res.json().catch(() => ({}));
  if (data?.csrfToken) {
    inMemoryCsrfToken = data.csrfToken;
  }
  return inMemoryCsrfToken;
}

// ─── Error type ──────────────────────────────────────────────────────────────

export class ApiError extends Error {
  /** HTTP status code */
  status;
  /** Backend `error` string */
  message;
  /** Backend `details` object (validation errors), if present */
  details;

  constructor(status, message, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.message = message;
    this.details = details;
  }
}

// ─── Core fetch wrapper ───────────────────────────────────────────────────────

/**
 * @param {string} path     — relative path, e.g. '/api/products/'
 * @param {RequestInit} options — fetch options (method, body, etc.)
 * @returns {Promise<any>}  — parsed JSON body on 2xx
 * @throws  {ApiError}      — on non-2xx responses
 */
async function request(path, options = {}) {
  const isMutating = options.method && options.method !== 'GET';
  const headers = {
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...(isMutating ? { 'X-CSRFToken': getCsrfToken() } : {}),
    ...options.headers,
  };

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers,
  });

  // 204 No Content
  if (res.status === 204) return null;

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new ApiError(res.status, data.error ?? 'Request failed.', data.details ?? null);
  }

  return data;
}

// ─── Auth endpoints ───────────────────────────────────────────────────────────
// Contracts from users/api_views.py

/**
 * POST /api/auth/login/
 * @param {{ username: string, password: string }} credentials
 * @returns {{ user: UserProfile }}
 */
export async function login(credentials) {
  const res = await request('/api/auth/login/', {
    method: 'POST',
    body: JSON.stringify(credentials),
  });
  if (res?.csrfToken) {
    inMemoryCsrfToken = res.csrfToken;
  }
  return res;
}

/**
 * POST /api/auth/logout/
 * @returns {{ detail: string }}
 */
export async function logout() {
  try {
    return await request('/api/auth/logout/', { method: 'POST' });
  } finally {
    inMemoryCsrfToken = '';
  }
}

/**
 * POST /api/auth/register/
 * @param {{ first_name, last_name, username, email?, password, password_confirm }} data
 * @returns {{ user: UserProfile }}
 */
export function register(data) {
  return request('/api/auth/register/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * GET /api/auth/profile/
 * @returns {{ user: UserProfile }}
 */
export function getProfile() {
  return request('/api/auth/profile/');
}

/**
 * PATCH /api/auth/profile/
 * @param {{ first_name?: string, last_name?: string, email?: string }} data
 * @returns {{ user: UserProfile }}
 */
export function updateProfile(data) {
  return request('/api/auth/profile/', {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * GET /api/auth/address/
 * @returns {{ address: { id, street_name, house_number, city, country } | null }}
 */
export function getAddress() {
  return request('/api/auth/address/');
}

/**
 * PUT /api/auth/address/
 * @param {{ street_name: string, house_number: string, city: string, country: string }} data
 * @returns {{ address: { id, street_name, house_number, city, country } }}
 */
export function saveAddress(data) {
  return request('/api/auth/address/', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// ─── Product endpoints (public) ───────────────────────────────────────────────
// Contracts from seller/api_views_v2.py

/**
 * GET /api/products/?search=&category=&page=
 * @param {{ search?: string, category?: string, page?: number }} params
 * @returns {{ count, page, num_pages, page_size, results: ProductList[] }}
 */
export function getProducts(params = {}) {
  const qs = new URLSearchParams();
  if (params.search)   qs.set('search', params.search);
  if (params.category) qs.set('category', params.category);
  if (params.page)     qs.set('page', String(params.page));
  const query = qs.toString() ? `?${qs}` : '';
  return request(`/api/products/${query}`);
}

/**
 * GET /api/products/<id>/
 * @returns {{ product: ProductDetail }}
 */
export function getProduct(id) {
  return request(`/api/products/${id}/`);
}

/**
 * GET /api/products/categories/
 * @returns {{ categories: { code: string, label: string }[] }}
 */
export function getCategories() {
  return request('/api/products/categories/');
}

// ─── Cart endpoints ───────────────────────────────────────────────────────────
// Contracts from cart/api_views.py + cart/serializers.py

/**
 * GET /api/cart/
 * @returns {{ cart: Cart }}
 */
export function getCart() {
  return request('/api/cart/');
}

/**
 * POST /api/cart/items/
 * @param {{ product_id: number, quantity: number }} item
 * @returns {{ cart: Cart }}
 */
export function addToCart(item) {
  return request('/api/cart/items/', {
    method: 'POST',
    body: JSON.stringify(item),
  });
}

/**
 * PATCH /api/cart/items/<id>/
 * @returns {{ cart: Cart }}
 */
export function updateCartItem(itemId, quantity) {
  return request(`/api/cart/items/${itemId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ quantity }),
  });
}

/**
 * DELETE /api/cart/items/<id>/
 * @returns {null}
 */
export function removeCartItem(itemId) {
  return request(`/api/cart/items/${itemId}/`, { method: 'DELETE' });
}

/**
 * DELETE /api/cart/
 * @returns {{ cart: Cart }}
 */
export function clearCart() {
  return request('/api/cart/', { method: 'DELETE' });
}

// ─── Order & Checkout endpoints ───────────────────────────────────────────────
// Contracts from orders/api_views.py + orders/serializers.py

/**
 * POST /api/checkout/
 * @param {{ shipping_address_id?: number }} [data]
 * @returns {{ order: Order }}
 */
export function checkout(data = {}) {
  return request('/api/checkout/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * GET /api/orders/
 * @returns {{ orders: Order[] }}
 */
export function getOrders() {
  return request('/api/orders/');
}

/**
 * GET /api/orders/<id>/
 * @returns {{ order: Order }}
 */
export function getOrder(id) {
  return request(`/api/orders/${id}/`);
}

// ─── Payment endpoints (Stripe) ───────────────────────────────────────────────
// Contracts from payments/api_views.py

/**
 * POST /api/payments/create-intent/<order_id>/
 * @param {number} orderId
 * @returns {{ client_secret: string, payment_intent_id: string, amount: number, currency: string, order_id: number }}
 */
export function createPaymentIntent(orderId) {
  return request(`/api/payments/create-intent/${orderId}/`, {
    method: 'POST',
  });
}

// ─── Seller endpoints ─────────────────────────────────────────────────────────
// Contracts from seller/api_views_v2.py and orders/api_views.py

/** GET /api/seller/profile/ */
export function getSellerProfile() {
  return request('/api/seller/profile/');
}

/** GET /api/seller/summary/ */
export function getSellerSummary() {
  return request('/api/seller/summary/');
}

/**
 * GET /api/seller/products/?search=&page=
 * @param {{ search?: string, page?: number }} params
 */
export function getSellerProducts(params = {}) {
  const qs = new URLSearchParams();
  if (params.search) qs.set('search', params.search);
  if (params.page)   qs.set('page', String(params.page));
  const query = qs.toString() ? `?${qs}` : '';
  return request(`/api/seller/products/${query}`);
}

/**
 * POST /api/seller/products/
 * @param {FormData | object} data
 */
export function createSellerProduct(data) {
  return request('/api/seller/products/', {
    method: 'POST',
    body: data instanceof FormData ? data : JSON.stringify(data),
  });
}

/** GET /api/seller/products/<id>/ */
export function getSellerProduct(id) {
  return request(`/api/seller/products/${id}/`);
}

/**
 * PATCH /api/seller/products/<id>/
 * @param {number} id
 * @param {FormData | object} data
 */
export function updateSellerProduct(id, data) {
  return request(`/api/seller/products/${id}/`, {
    method: 'PATCH',
    body: data instanceof FormData ? data : JSON.stringify(data),
  });
}

/**
 * DELETE /api/seller/products/<id>/ (soft-deactivate)
 */
export function deleteSellerProduct(id) {
  return request(`/api/seller/products/${id}/`, {
    method: 'DELETE',
  });
}

/** GET /api/seller/orders/ */
export function getSellerOrders() {
  return request('/api/seller/orders/');
}

/**
 * POST /api/seller/orders/<id>/status/
 * @param {number} orderId
 * @param {"pending" | "processing" | "shipped" | "cancelled"} status
 */
export function updateSellerOrderStatus(orderId, orderStatus) {
  return request(`/api/seller/orders/${orderId}/status/`, {
    method: 'POST',
    body: JSON.stringify({ order_status: orderStatus }),
  });
}

// ─── Admin endpoints ──────────────────────────────────────────────────────────
// Contracts from seller/api_views_v2.py, orders/api_views.py, users/api_views.py

/**
 * GET /api/admin/products/?search=&category=&active=&page=
 */
export function getAdminProducts(params = {}) {
  const qs = new URLSearchParams();
  if (params.search)   qs.set('search', params.search);
  if (params.category) qs.set('category', params.category);
  if (params.active !== undefined && params.active !== '') qs.set('active', String(params.active));
  if (params.seller_id) qs.set('seller_id', String(params.seller_id));
  if (params.page)     qs.set('page', String(params.page));
  const query = qs.toString() ? `?${qs}` : '';
  return request(`/api/admin/products/${query}`);
}

/** PATCH /api/admin/products/<id>/activate/ */
export function activateAdminProduct(id) {
  return request(`/api/admin/products/${id}/activate/`, {
    method: 'PATCH',
  });
}

/** GET /api/admin/orders/ */
export function getAdminOrders() {
  return request('/api/admin/orders/');
}

/**
 * GET /api/admin/users/?search=&role=
 */
export function getAdminUsers(params = {}) {
  const qs = new URLSearchParams();
  if (params.search) qs.set('search', params.search);
  if (params.role)   qs.set('role', params.role);
  const query = qs.toString() ? `?${qs}` : '';
  return request(`/api/admin/users/${query}`);
}

/**
 * PATCH /api/admin/users/<id>/role/
 * @param {number} userId
 * @param {"buyer" | "seller"} role
 */
export function assignUserRole(userId, role) {
  return request(`/api/admin/users/${userId}/role/`, {
    method: 'PATCH',
    body: JSON.stringify({ role }),
  });
}

/** GET /api/admin/summary/ */
export function getAdminSummary() {
  return request('/api/admin/summary/');
}

// ─── Health ───────────────────────────────────────────────────────────────────

/** GET /api/health/ */
export function healthCheck() {
  return request('/api/health/');
}

// ─── B2B Wholesale Platform Endpoints ────────────────────────────────────────

/** GET /api/b2b/bakeries/ */
export function getB2BBakeries() {
  return request('/api/b2b/bakeries/');
}

/** GET /api/b2b/bakeries/<id>/catalogue/ */
export function getB2BBakeryCatalogue(bakeryId) {
  return request(`/api/b2b/bakeries/${bakeryId}/catalogue/`);
}

/** POST /api/b2b/bakeries/<id>/authorize/ */
export function authorizeB2BBakery(bakeryId) {
  return request(`/api/b2b/bakeries/${bakeryId}/authorize/`, {
    method: 'POST',
  });
}

/**
 * POST /api/b2b/orders/create/
 * @param {{ bakery_id: number, items: Array<{ product_id: number, quantity: number }>, notes?: string, delivery_address?: string }} payload
 */
export function createB2BOrder(payload) {
  return request('/api/b2b/orders/create/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/** GET /api/b2b/orders/?status= */
export function getB2BOrders(status = '') {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  return request(`/api/b2b/orders/${query}`);
}

/** GET /api/b2b/orders/<id>/ */
export function getB2BOrderDetail(orderId) {
  return request(`/api/b2b/orders/${orderId}/`);
}

/** POST /api/b2b/orders/<id>/repeat/ */
export function repeatB2BOrder(orderId) {
  return request(`/api/b2b/orders/${orderId}/repeat/`, {
    method: 'POST',
  });
}

/** POST /api/b2b/orders/<id>/receipt/ */
export function confirmB2BReceipt(orderId) {
  return request(`/api/b2b/orders/${orderId}/receipt/`, {
    method: 'POST',
  });
}

/** GET /api/b2b/bakery/orders/?status= */
export function getBakeryIncomingOrders(status = '') {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  return request(`/api/b2b/bakery/orders/${query}`);
}

/**
 * POST /api/b2b/bakery/orders/<id>/action/
 * @param {number} orderId
 * @param {{ action: 'confirm'|'reject'|'prepare'|'dispatch', rejection_reason?: string, dispatch_notes?: string }} payload
 */
export function actionBakeryOrder(orderId, payload) {
  return request(`/api/b2b/bakery/orders/${orderId}/action/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/** GET /api/b2b/bakery/dealers/ */
export function getBakeryConnectedDealers() {
  return request('/api/b2b/bakery/dealers/');
}

/** GET /api/b2b/bakery/profile/ */
export function getBakeryProfile() {
  return request('/api/b2b/bakery/profile/');
}

/** PUT /api/b2b/bakery/profile/ */
export function updateBakeryProfile(data) {
  return request('/api/b2b/bakery/profile/', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/** GET /api/b2b/dealer/profile/ */
export function getDealerProfile() {
  return request('/api/b2b/dealer/profile/');
}

/** PUT /api/b2b/dealer/profile/ */
export function updateDealerProfile(data) {
  return request('/api/b2b/dealer/profile/', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/** GET /api/b2b/admin/summary/ */
export function getAdminB2BSummary() {
  return request('/api/b2b/admin/summary/');
}
