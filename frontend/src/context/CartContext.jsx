/**
 * CartContext — client-side cart state for BakeCart 2.0.
 *
 * Cart data is always loaded from the backend (GET /api/cart/) and never
 * synthesised client-side. The cart is re-fetched after every mutation so
 * the UI always reflects the server's authoritative state.
 *
 * Cart shape from backend (cart/serializers.py):
 *   {
 *     id, created_at, updated_at,
 *     grand_total: string,
 *     items: [
 *       { id, product_id, product_title, unit_price, quantity, line_total }
 *     ]
 *   }
 *
 * The context exposes the raw cart object (null if not loaded), plus
 * derived itemCount for navigation badge use.
 *
 * Cart is only loaded when the user is authenticated (the backend returns
 * 403 for unauthenticated cart requests).
 */

import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { getCart, addToCart as apiAdd, updateCartItem as apiUpdate,
         removeCartItem as apiRemove, clearCart as apiClear } from '../api/client';
import { useAuth } from './AuthContext';

const CartContext = createContext(null);

export function CartProvider({ children }) {
  const { user } = useAuth();
  const [cart, setCart]       = useState(null);
  const [cartLoading, setCartLoading] = useState(false);
  const [cartError, setCartError]     = useState(null);

  const loadCart = useCallback(async () => {
    setCartLoading(true);
    setCartError(null);
    try {
      const data = await getCart();
      setCart(data.cart);
    } catch (err) {
      setCartError(err.message ?? 'Could not load cart.');
    } finally {
      setCartLoading(false);
    }
  }, []);

  // Load cart whenever the authenticated user changes.
  useEffect(() => {
    if (user) {
      loadCart();
    } else {
      setCart(null);
    }
  }, [user, loadCart]);

  async function addToCart(productId, quantity) {
    const data = await apiAdd({ product_id: productId, quantity });
    setCart(data.cart);
    return data.cart;
  }

  async function updateItem(itemId, quantity) {
    const data = await apiUpdate(itemId, quantity);
    setCart(data.cart);
    return data.cart;
  }

  async function removeItem(itemId) {
    await apiRemove(itemId);
    // Reload to get updated grand_total; DELETE /api/cart/items/<id>/ returns 204.
    await loadCart();
  }

  async function clearCart() {
    const data = await apiClear();
    setCart(data.cart);
  }

  const itemCount = cart?.items?.reduce((sum, i) => sum + i.quantity, 0) ?? 0;

  return (
    <CartContext.Provider value={{
      cart, cartLoading, cartError,
      itemCount, loadCart,
      addToCart, updateItem, removeItem, clearCart,
    }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart must be used inside <CartProvider>');
  return ctx;
}
