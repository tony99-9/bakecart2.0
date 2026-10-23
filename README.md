# BakeCart 2.0 🎂🥖

**BakeCart 2.0** is a full-stack B2B bakery marketplace and retail e-commerce platform. It connects **Dealers (Suppliers)** selling commercial ingredients and bakery items to **Bakery Owners (Buyers)** purchasing products in wholesale quantities, alongside a public storefront and an administrative control panel.

---

## 🚀 Key Highlights & Architecture

- **Decoupled Architecture**: Modern React 18 SPA powered by Vite paired with a Django REST Framework (DRF) backend.
- **Role-Based Workflows**:
  - **Dealer (Supplier)**: Manage product inventory, wholesale units (boxes, crates, trays), minimum order quantities (MOQ), and incoming purchase orders through a dedicated dispatch lifecycle (*Confirmed ➔ In Preparation ➔ Dispatched*).
  - **Bakery Owner (Buyer)**: Browse dealer catalogues, issue digital purchase orders, repeat past orders with live stock verification, and confirm receipt.
  - **Admin**: System-wide dashboard for user role assignment, catalogue moderation, and platform order ledger.
  - **Retail Customer**: Browse storefront catalogues with rich filtering, search, cart management, and Stripe checkout.
- **Modern Storefront UI**:
  - High-res bakery hero banner with floating callouts.
  - Horizontal interactive category strip (Cakes, Cupcakes, Breads, Cookies, Pastries, Donuts, Brownies, Pies, Gift Hampers).
  - Responsive 6-item featured grid with real-time stock status, wishlist heart toggle, star ratings, and bakery origin pins.
  - 4-point value proposition strip for service guarantees.
- **Server-Authoritative State & Security**:
  - Django session-based authentication with cross-origin CSRF protection (`X-CSRFToken`).
  - Server-calculated cart totals and server-verified inventory validation on order placement.
  - Stripe Payment Intent integration with webhook signature verification.
- **Comprehensive Test Suite**:
  - 166 automated unit and integration tests passing (`python manage.py test`).

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, Vite, React Router 6, Vanilla CSS Design System, Context API |
| **Backend** | Python 3, Django 4.2+, Django REST Framework (DRF) |
| **Database** | SQLite (development) / PostgreSQL compatible |
| **Payments** | Stripe API (`PaymentIntent` + Webhooks) |
| **Media & Images** | Pillow (automatic aspect-ratio cropping and thumbnails) |
| **Testing** | Django TestCase (`166 tests passed`) |

---

## 📂 Project Structure

```text
bakecart/
├── frontend/                   # React 18 + Vite Single Page Application
│   ├── src/
│   │   ├── api/client.js       # Centralized API fetch wrapper with CSRF injection
│   │   ├── components/         # Reusable UI, Layout, Navbar, ProductCard
│   │   ├── context/            # AuthContext, CartContext
│   │   └── pages/              # Home, Shop, Bakeries, Orders, Admin, Seller, Auth
│   ├── public/                 # Static assets, hero imagery
│   └── package.json
│
├── sir_cake/                   # Django REST Framework Backend
│   ├── b2b/                    # B2B order desk, dealership authorizations, repeat orders
│   ├── cart/                   # Server-authoritative shopping cart
│   ├── orders/                 # Order ledger, status transitions, dispatch tracking
│   ├── payments/               # Stripe payment intent creation & webhook handlers
│   ├── seller/                 # Dealer inventory, wholesale units, product catalogue
│   ├── users/                  # User registration, role assignments, profile & address
│   ├── sir_cake/               # Project configuration, URLs, health checks, settings
│   └── manage.py
│
├── .env.example                # Example environment variables
└── requirements.txt            # Python dependencies
```

---

## ⚡ Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+** and **npm**

---

### 2. Backend Setup (Django)

```bash
# Navigate to the backend directory
cd sir_cake

# Create and activate virtual environment
python3 -m venv ../venv
source ../venv/bin/activate

# Install dependencies
pip install -r ../requirements.txt

# Run migrations
python manage.py migrate

# (Optional) Run the 166 automated tests
python manage.py test --noinput

# Start the Django development server
python manage.py runserver 127.0.0.1:8000
```

Backend will be live at `http://127.0.0.1:8000`.

---

### 3. Frontend Setup (React + Vite)

```bash
# In a separate terminal, navigate to the frontend directory
cd frontend

# Install npm dependencies
npm install

# Start Vite development server
npm run dev
```

Frontend will be accessible at `http://localhost:5173`.

---

## 🔑 Default Roles & Accounts

When creating or testing accounts:
- **Bakery Owner (Buyer)**: Default registration role. Can browse dealer catalogues, order wholesale products, and use the order desk.
- **Dealer (Supplier)**: Set `is_dealer = True` or assign via the Admin Portal (`/admin/users`). Can manage catalogue items, set minimum order quantities (MOQ), and fulfill orders.
- **Superuser / Admin**: Run `python manage.py createsuperuser` to access the Django admin and the frontend `/admin/summary` portal.

---

## 🧪 Running Tests

To verify backend integrity, run:

```bash
cd sir_cake
python manage.py test --noinput
```

Output:
```text
Ran 166 tests in 10.676s
OK
```

---

## 📄 License
This project is open-source under the MIT License.
