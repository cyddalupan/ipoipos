# Ipo-Ipo POS — Project TODO

## Done

- [x] **Staff model with role-based access** (Card: `Add User/Staff model and admin CRUD for cashier accounts`)
  - `Staff` model (`pos/models.py`) — OneToOneField to `auth.User` + role (`ADMIN`/`CASHIER`)
  - Migration `pos/migrations/0003_staff.py`
  - `pos/admin.py` — CustomUserAdmin with Staff inline CRUD
  - 7 unit tests in `pos/tests.py` (StaffModelTest)
  - Updated `README.md` with Staff model documentation and auth section
  - Created `TODO.md`

- [x] **Login page and authentication for POS users** (Card: `Add login page and authentication for POS users`)
  - Login at `/login/` (Django `LoginView` subclass — `CustomLoginView`)
  - Logout at `/logout/` (custom view accepting GET & POST)
  - Home dashboard protected with `@login_required`
  - All CBVs (`InventoryDashboardView`, `CategoryListView`, `DiscountTypeListView`, inventory CRUD, etc.) protected with `LoginRequiredMixin`
  - Template `templates/registration/login.html` with dark theme, branding, and error display
  - Sidebar footer shows logged-in username and Logout link
  - 21 tests in `pos.tests.LoginPageTest` — all passing
  - Updated `README.md` with authentication flow documentation

- [x] **Add table number selection (1-20) to POS checkout** (Card: `Add table number selection (1-20) to POS checkout`)
  - `table_number` field already present on Transaction model (migration `0006_transaction_table_number`)
  - `CheckoutEngine` accepts `table_number` param with range validation (1-20) raising `ValueError` for out-of-range
  - API endpoint `/api/checkout/` accepts `table_number` in JSON payload
  - 10 table number tests in `pos.tests.CheckoutEngineTest`: storage, defaults, API integration, range validation (below 1, above 20, boundary values, null)
  - All tests passing
  - Updated `README.md` with table_number field and validation docs

- [x] **Add dine-in/takeout toggle to POS checkout flow** (Card: `Add dine-in/takeout toggle to POS checkout flow`)
  - `order_type` field on Transaction model (CharField, choices: DINE_IN/TAKE_OUT, default DINE_IN)
  - Migration `pos/migrations/0007_transaction_order_type.py`
  - `CheckoutEngine` accepts `order_type` param with set validation (raises ValueError for invalid types)
  - API endpoint `/api/checkout/` accepts `order_type` in JSON payload (defaults to DINE_IN)
  - 5 order_type tests in `pos.tests.CheckoutEngineTest`: default, DINE_IN stored, TAKE_OUT stored, API integration, invalid type rejected
  - All tests passing
  - Updated `README.md` with order_type field and validation docs

- [x] **Add MealSubcategory (food group) model and filter items by group** (Card: `Add MealSubcategory (food group) model and filter items by group`)
  - `MealSubcategory` model (`pos/models.py`) — name, slug, emoji fields; unique name & slug constraints
  - Migration `pos/migrations/0004_mealsubcategory_item_meal_subcategory.py`
  - `meal_subcategory` ForeignKey on `Item` (nullable, `SET_NULL` on delete)
  - `pos/admin.py` — `MealSubcategoryAdmin` with search by name, `ItemAdmin` updated with `meal_subcategory` in list_display/list_filter/search_fields
  - `product_catalog` view in `pos/views.py` supports `?subcategory=slug` filter, passes `subcategories` queryset and `current_subcategory` to template
  - Template `pos/templates/pos/products.html` — subcategory dropdown filter UI with emoji labels, clear filter link
  - Seed data migration `pos/migrations/0005_seed_mealsubcategories.py` — 9 default groups (Chicken, Pork, Beef, Vegetables, Rice, Drinks, Seafood, Noodles, Desserts)
  - 12 unit tests in `pos.tests` (MealSubcategoryModelTest 4, MealSubcategoryOnItemTest 3, MealSubcategoryAdminTest 2, MealSubcategoryFilterTest 3) — all passing
  - Updated `README.md` with MealSubcategory model, Item subcategory field, and seed data

- [x] **Shift Management** — Shift model (cashier, start/end times, float, status OPEN/CLOSED), migration 0010, admin registration, 3 API endpoints (start/end/current), shift FK on Transaction, checkout API accepts shift_id
  - 19 tests (ShiftModelTest 5, ShiftAPITest 9, ShiftTransactionTest 5) — all passing
  - Updated README.md with shift management documentation

- [x] **Shift Expense Tracking** (Card: `Add shift expense tracking with manual entry`)
  - `Expense` model (shift FK, amount, description, category, created_at)
  - Migration `pos/migrations/0012_expense.py`
  - Admin registration with filtering by shift and category
  - API (GET/POST) at `/api/shifts/<shift_id>/expenses/`
  - 17 tests (ExpenseModelTest 5 + ExpenseAPITest 12) — all passing
  - Updated README.md with expense API docs

## Done

- [x] **Void/Refund Support** (Card: `Add void/refund support to Ipo-Ipo POS transactions`)
  - `Transaction` model: `status` choices include "VOIDED", `void_reason` and `voided_at` fields (migration 0013)
  - `TransactionVoidView` (POST `/transactions/<pk>/void/`) — ADMIN-only, stock reinstatement, reason capture, zeroes totals
  - POS dashboard: `clearCart()` button before checkout
  - Sales history: Void button per transaction with reason modal
  - Receipt reprint: VOID watermark overlay + red badge on VOIDED receipts
  - 5 tests (TransactionVoidUrlTest + TransactionVoidTest) — all passing

- [x] **Phase 7: Branch Foundation** (Card: `Ipo-iPOS version 1` checklist)
  - `Branch` model with LPG/AGRI/GAS types, code, tax_rate, currency, address, contact
  - Migration 0016 (Branch model) + 0017 (branch FK on Item, Transaction, Shift, Staff)
  - Full Branch CRUD at `/branches/` (list, add, edit, delete)
  - Admin registration at `/admin/pos/branch/`
  - Branch selection landing page (`/`) — pick branch before accessing POS
  - Session-based current branch, redirects to branch select if none chosen
  - Dashboard scoped to current branch (sales, items, stats)
  - Branch indicator + switch button in sidebar
  - Inventory dashboard/CRUD scoped to current branch
  - Sales history scoped to current branch
  - Product catalog scoped to current branch
  - Shift start/current scoped to current branch
  - Transactions assigned to branch on checkout
  - "Change Branch" button on dashboard topbar

## Future / Follow-up

- [ ] Write permission checks for admin-only views (e.g., admin panel, inventory management)
- [ ] Pre-existing test failure: `test_category_delete_protected_handles_error` — the delete page renders without the "protected" message on POST with ProtectedError
- [ ] Fix `ViewSmokeTest` failures — tests need `self.client.login()` for protected views, and test data setup for dashboard stats tests
