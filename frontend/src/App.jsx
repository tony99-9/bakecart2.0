import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { CartProvider } from './context/CartContext';
import Layout from './components/Layout/Layout';
import { PageLoader } from './components/UI';

/**
 * Code-split each page so the initial bundle stays small.
 * Suspense + PageLoader provides the loading UI during lazy import.
 */
const HomePage              = lazy(() => import('./pages/Home/HomePage'));
const BakeriesPage          = lazy(() => import('./pages/Bakeries/BakeriesPage'));
const BakeryCataloguePage   = lazy(() => import('./pages/Bakeries/BakeryCataloguePage'));
const WholesaleOrderDeskPage = lazy(() => import('./pages/Orders/WholesaleOrderDeskPage'));
const ShopPage              = lazy(() => import('./pages/Shop/ShopPage'));
const ProductDetailPage     = lazy(() => import('./pages/ProductDetail/ProductDetailPage'));
const CartPage              = lazy(() => import('./pages/Cart/CartPage'));
const CheckoutPage          = lazy(() => import('./pages/Checkout/CheckoutPage'));
const OrderListPage         = lazy(() => import('./pages/Orders/OrderListPage'));
const OrderDetailPage       = lazy(() => import('./pages/Orders/OrderDetailPage'));
const ProfilePage           = lazy(() => import('./pages/Profile/ProfilePage'));
const SellerOverviewPage    = lazy(() => import('./pages/Seller/SellerOverviewPage'));
const SellerProductsPage    = lazy(() => import('./pages/Seller/SellerProductsPage'));
const SellerProductFormPage = lazy(() => import('./pages/Seller/SellerProductFormPage'));
const SellerOrdersPage      = lazy(() => import('./pages/Seller/SellerOrdersPage'));
const BakeryProfilePage     = lazy(() => import('./pages/Seller/BakeryProfilePage'));
const AdminSummaryPage      = lazy(() => import('./pages/Admin/AdminSummaryPage'));
const AdminUsersPage        = lazy(() => import('./pages/Admin/AdminUsersPage'));
const AdminProductsPage     = lazy(() => import('./pages/Admin/AdminProductsPage'));
const AdminOrdersPage       = lazy(() => import('./pages/Admin/AdminOrdersPage'));
const LoginPage             = lazy(() => import('./pages/Auth/LoginPage'));
const RegisterPage          = lazy(() => import('./pages/Auth/RegisterPage'));
const NotFoundPage          = lazy(() => import('./pages/NotFound/NotFoundPage'));

export default function App() {
  return (
    <BrowserRouter>
      {/*
        AuthProvider must wrap CartProvider because CartProvider
        depends on useAuth() to know when to load the cart.
      */}
      <AuthProvider>
        <CartProvider>
          <Layout>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/"              element={<HomePage />} />
                {/* B2B Wholesale Routes */}
                <Route path="/bakeries"                 element={<BakeriesPage />} />
                <Route path="/bakeries/:id"             element={<BakeryCataloguePage />} />
                <Route path="/wholesale-order"          element={<WholesaleOrderDeskPage />} />

                <Route path="/shop"          element={<ShopPage />} />
                <Route path="/products/:id"  element={<ProductDetailPage />} />
                <Route path="/cart"          element={<CartPage />} />
                <Route path="/checkout"      element={<CheckoutPage />} />
                <Route path="/orders"                  element={<OrderListPage />} />
                <Route path="/orders/:id"              element={<OrderDetailPage />} />
                <Route path="/profile"                 element={<ProfilePage />} />
                {/* Seller routes */}
                <Route path="/seller/overview"          element={<SellerOverviewPage />} />
                <Route path="/seller/products"          element={<SellerProductsPage />} />
                <Route path="/seller/products/new"      element={<SellerProductFormPage />} />
                <Route path="/seller/products/:id/edit" element={<SellerProductFormPage />} />
                <Route path="/seller/orders"            element={<SellerOrdersPage />} />
                <Route path="/seller/profile"           element={<BakeryProfilePage />} />
                {/* Admin routes */}
                <Route path="/admin/summary"            element={<AdminSummaryPage />} />
                <Route path="/admin/users"              element={<AdminUsersPage />} />
                <Route path="/admin/products"           element={<AdminProductsPage />} />
                <Route path="/admin/orders"             element={<AdminOrdersPage />} />
                <Route path="/login"                   element={<LoginPage />} />
                <Route path="/register"                element={<RegisterPage />} />
                {/* catch-all */}
                <Route path="*"              element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </Layout>
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
