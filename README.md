## Ipo-iPOS — Django POS & Inventory System
### Full Functional & Architectural Documentation
> **Brand:** teal/cyan theme with dark sidebar — uses 🌪️ tornado emoji and an SVG tornado icon throughout. Logo at `static/pos/logo.svg`, favicon at `static/pos/favicon.png`.
> ⚡ **Offline-First Desktop App** — Designed to run on localhost via `python manage.py runserver`, used through Chrome's "Save as Desktop App" feature (no internet required after install). Staff management via Django admin (`/admin/`). No POS login required.
> 🧭 **Sidebar Navigation** — All pages render the same sidebar from a single `base.html` template using `{% url %}` tags (not context variables), so links work everywhere. Includes Premium Cloud upgrade CTA section.
> 🎨 **Theme Design** — Redesigned 2026-06-23: teal (`#0d9488`) / cyan primary, dark sidebar (`#1a1a2e`), white/light content area, SVG outline icons, glass card variants, animated notifications, refined scrollbar. Premium upgrade CTA in sidebar. All standalone pages (discounts, customers, inventory) use shared `base.html`.
> 🔍 **Standalone Pages:** The discount CRUD pages were migrated from standalone purple-themed templates to the shared `base.html` layout. Item form, inventory dashboard, category pages already extended `base.html`.

### Architecture Overview

![System Architecture](docs/architecture.png)

```
+---------------------------------------------------------------+
|                    LOCAL MACHINE TERMINAL                      |
|                                                                |
|  +--[Google Chrome -> Save as Desktop App]---+                 |
|  |  App Mode (No address bar, Windowed)       |                 |
|  +---------------------+----------------------+                 |
|                        |                                       |
|                localhost:8000                                   |
|                        v                                       |
|  +---------------------+----------------------+                 |
|  |         Django Core Web Engine              |                |
|  |  [URLs] -> [Views] -> [Forms] -> [Signals] |                |
|  +---------------------+----------------------+                 |
|                        |                                       |
|                  ORM (SQLite WAL)                               |
|  +---------------------+----------------------+                 |
|  |  SQLite Database (Easy backup — just copy) |                |
|  +--------------------------------------------+                 |
+---------------------------------------------------------------+
```

#### Application Runtime Stack
- **Core Frame:** Django Monolith (Python 3.11+) — offline-first transactional app.
- **Database:** SQLite with **Write-Ahead Logging (WAL)** mode for parallel reads + safe transaction isolation.
- **Client:** Google Chrome "Save as Desktop App" — full-screen kiosk-like experience, no address bar, no chrome elements.
- **UI Layer:** Server-side Django HTML Templates with lightweight utility CSS. No heavy frontend framework. Zero external API dependencies — works completely offline.
- **Backup:** Simply copy the `db.sqlite3` file — all your data in one portable file.

### 0. Offline Operation (No Authentication)

Ipo-iPOS runs completely offline with **zero authentication required**:
- No login page, no logout, no sessions
- All views are publicly accessible
- Shift cashier names are provided inline when starting a shift
- Void operations require no special role
- Staff model still works for record-keeping via Django admin (`/admin/`)

**Creating staff accounts**:
1. Go to `/admin/` and log in with a superuser account
2. Navigate to **Staff** section
3. Create a new Staff record — this automatically creates a linked Django `User`
4. Open `http://localhost:8000` — no login required, start taking orders immediately!

**Note**: Authentication-related tests were removed since Ipo-iPOS operates offline without login.

### 1. How to Deploy as a Desktop App

1. **Run the server:**
   ```bash
   cd /path/to/ipoipo-pos
   source venv/bin/activate
   python manage.py runserver 0.0.0.0:8000
   ```
2. **Open in Chrome** and navigate to `http://localhost:8000`
3. **Save as desktop app:**
   - Click the three-dot menu (⋮) → **Save and Share** → **Install page as app...**
   - Or: ⋮ → **Cast, save, and share** → **Install page as app...**
   - Name it "Ipo-iPOS"
   - Chrome creates a standalone desktop shortcut — opens windowed, no address bar
4. **Done.** No internet. Opens straight to POS.

### 2. Database Schema

SQLite with WAL mode. Backup: just copy `db.sqlite3`.

```python
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

class Staff(models.Model):
    """Extends Django's auth User with role-based access for POS staff."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        CASHIER = "CASHIER", "Cashier"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff")
    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.CASHIER
    )

    def save(self, *args, **kwargs):
        if not self.user.is_superuser:
            self.user.is_staff = True
            self.user.save(update_fields=["is_staff"])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} \u2014 {self.get_role_display()}"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    # Products get their emoji/image from the Item, not Category

    def __str__(self):
        return self.name

class Item(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='items')
    meal_subcategory = models.ForeignKey(
        MealSubcategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="items",
        help_text="Food group/meal subcategory for POS product filtering"
    )
    name = models.CharField(max_length=150, unique=True)
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU/Barcode")
    emoji = models.CharField(max_length=10, blank=True, null=True,
                             help_text="Emoji for visual display (e.g., 🍗🍚🥤)")
    image = models.ImageField(upload_to='product_images/', blank=True, null=True,
                               help_text="Product image (optional, emoji used as fallback)")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_qty = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)

    def display_icon(self):
        """Returns emoji if set, otherwise a generic icon."""
        return self.emoji or "📦"

    def __str__(self):
        return f"{self.display_icon()} {self.name} ({self.sku})"

class MealSubcategory(models.Model):
    """
    Food group / meal subcategory for grouping food items and POS product filtering.
    Provides an emoji-labeled category layer under Item for visual product catalog organization.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    emoji = models.CharField(max_length=10, blank=True, default="",
                             help_text="Emoji for visual display (e.g., 🍗🍚🥤)")

    def __str__(self):
        return f"{self.emoji} {self.name}"

class DiscountType(models.Model):
    DISCOUNT_CHOICES = [
        ('PERCENTAGE', 'Percentage Based'),
        ('FIXED', 'Fixed Cash Value'),
        ('PH_SPECIAL', 'Philippine Statutory (Senior/PWD)'),
    ]
    name = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=20, choices=DISCOUNT_CHOICES, default='PERCENTAGE')
    value = models.DecimalField(max_digits=10, decimal_places=2,
                                help_text="Percentage value or exact cash deduction amount.")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.get_kind_display()}"

class Transaction(models.Model):
    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('DIGITAL', 'Digital Wallet (GCash/Maya)'),
    ]
    timestamp = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_applied = models.ForeignKey(DiscountType, on_delete=models.PROTECT, null=True, blank=True)
    ORDER_TYPES = [
        ("DINE_IN", "Dine-In"),
        ("TAKE_OUT", "Take-Out"),
    ]
    order_type = models.CharField(
        max_length=10, choices=ORDER_TYPES, default="DINE_IN",
        help_text="Order fulfillment type: DINE_IN or TAKE_OUT"
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vat_exclusive_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_digits=10, choices=PAYMENT_METHODS, default='CASH')
    reference_number = models.CharField(max_length=100, blank=True, null=True,
                                         help_text="Trace ID for GCash/Maya validation")
    total_diners = models.PositiveIntegerField(default=1)
    special_cardholders_count = models.PositiveIntegerField(default=0)
    vat_inclusive = models.BooleanField(
        default=True,
        help_text="If True, 12% VAT is computed from the vatable amount. "
                  "If False, prices are VAT-exclusive (no VAT added)."
    )
    table_number = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Dining table number (1-20), null for takeout"
    )
    manual_discount_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Manual percentage discount (0-100%) applied to subtotal before VAT"
    )

    def __str__(self):
        return f"TXN-{self.id} | {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class TransactionItem(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='line_items')
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)
```

**Key changes:**
- ✅ `Staff` model (OneToOneField to `auth.User`) with roles: `ADMIN` / `CASHIER`
- ✅ Staff are created/managed via Django admin (`/admin/`)
- ✅ `emoji` field on Item for visual product display
- ✅ `image` field for product photos (emoji fallback)
- ✅ `order_type` field on Transaction (CharField, choices: DINE_IN/TAKE_OUT, default DINE_IN)
- ✅ `table_number` field on Transaction (PositiveSmallIntegerField, nullable, range 1-20 validated in CheckoutEngine)
- ✅ `manual_discount_pct` field on Transaction (DecimalField, nullable, 0-100%) — free-text percentage discount applied to subtotal before VAT
- ✅ SQLite — just copy the file for backup

### 3a. Manual Percentage Discount

A free-text percentage discount field on the `Transaction` model (`manual_discount_pct`,
DecimalField, 0-100%) that is **independent** from the preset `DiscountType` system.
The cashier can enter any percentage off the subtotal without needing a predefined
discount type.

**Behavior:**
- Applied to the **subtotal before VAT** (reduces the vatable base)
- Validated on the model (0-100%) and in `CheckoutEngine`
- When set alongside a `DiscountType`, the manual discount reduces the subtotal first,
  then the preset discount is applied
- Stored as `manual_discount_pct` on the Transaction for audit trail

**API payload (POST /pos/api/checkout/):**
```json
{
  "cart": [{"item_id": 1, "quantity": 2}],
  "payment_method": "CASH",
  "manual_discount_pct": 10.00
}
```

**API response now includes:**
```json
{
  "status": "success",
  "transaction_id": 42,
  "grand_total": "180.00",
  "discount_amount": "20.00",
  "manual_discount_pct": "10.00"
}
```

### 3b. Business Logic: Checkout Engine & Discounts

```python
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction as db_transaction
from .models import Item, Transaction, TransactionItem

class CheckoutEngine:
    TABLE_MIN = 1
    TABLE_MAX = 20

    VALID_ORDER_TYPES = {"DINE_IN", "TAKE_OUT"}

    def __init__(self, cart_data, discount_id=None, payment_method='CASH',
                 ref_num=None, total_diners=1, special_count=0,
                 table_number=None, order_type='DINE_IN',
                 vat_inclusive=True, manual_discount_pct=None):
        """
        cart_data format: [{'item_id': 1, 'qty': 2}, {'item_id': 2, 'qty': 1}]
        Cashier captured via session (future: link to Staff model).
        table_number: dining table (1-20) or None for takeout.
        order_type: 'DINE_IN' or 'TAKE_OUT' (default DINE_IN).
        vat_inclusive: bool (default True). When True, 12% VAT is computed
                       from vatable amounts. When False, no VAT is applied.
        manual_discount_pct: Decimal or None. Free-text percentage (0-100)
                             applied to subtotal before VAT.
        Validated in process(): must be valid order_type, table 1-20 or None.
        """
        self.cart_data = cart_data
        self.discount_id = discount_id
        self.payment_method = payment_method
        self.ref_num = ref_num
        self.total_diners = total_diners
        self.special_count = special_count
        self.table_number = table_number
        self.order_type = order_type

        self.subtotal = Decimal('0.00')
        self.discount_amount = Decimal('0.00')
        self.vat_exempt_sales = Decimal('0.00')
        self.vat_amount = Decimal('0.00')
        self.grand_total = Decimal('0.00')

    def calculate_totals(self, discount_obj):
        for entry in self.cart_data:
            item = Item.objects.get(id=entry['item_id'])
            self.subtotal += item.selling_price * Decimal(entry['qty'])

        if discount_obj and discount_obj.is_active:
            if discount_obj.kind == 'PERCENTAGE':
                self.discount_amount = (self.subtotal * (discount_obj.value / Decimal('100.00'))).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                vtable_balance = self.subtotal - self.discount_amount
                self.vat_exclusive_sales = (vtable_balance / Decimal('1.12')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                self.vat_amount = vtable_balance - self.vat_exclusive_sales
                self.grand_total = vtable_balance

            elif discount_obj.kind == 'FIXED':
                self.discount_amount = discount_obj.value
                vtable_balance = max(Decimal('0.00'), self.subtotal - self.discount_amount)
                self.vat_exclusive_sales = (vtable_balance / Decimal('1.12')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                self.vat_amount = vtable_balance - self.vat_exclusive_sales
                self.grand_total = vtable_balance

            elif discount_obj.kind == 'PH_SPECIAL':
                # PH Senior/PWD statutory discount formula
                gross_share = (self.subtotal / Decimal(self.total_diners)) * Decimal(self.special_count)
                vat_component_in_share = (gross_share - (gross_share / Decimal('1.12'))).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                exempt_base = (gross_share / Decimal('1.12')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                law_discount = (exempt_base * Decimal('0.20')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)

                self.discount_amount = law_discount
                self.grand_total = (self.subtotal - vat_component_in_share - law_discount).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                self.vat_exclusive_sales = (self.grand_total / Decimal('1.12')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                self.vat_amount = self.grand_total - self.vat_exclusive_sales
        else:
            self.vat_exclusive_sales = (self.subtotal / Decimal('1.12')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
            self.vat_amount = self.subtotal - self.vat_exclusive_sales
            self.grand_total = self.subtotal

    def process(self):
        from .models import DiscountType
        discount_obj = DiscountType.objects.get(id=self.discount_id) if self.discount_id else None

        with db_transaction.atomic():
            self.calculate_totals(discount_obj)

            txn = Transaction.objects.create(
                subtotal=self.subtotal,
                discount_applied=discount_obj,
                discount_amount=self.discount_amount,
                vat_exclusive_sales=self.vat_exclusive_sales,
                vat_amount=self.vat_amount,
                grand_total=self.grand_total,
                payment_method=self.payment_method,
                reference_number=self.ref_num,
                total_diners=self.total_diners,
                special_cardholders_count=self.special_count
            )

            for entry in self.cart_data:
                item = Item.objects.select_for_update().get(id=entry['item_id'])
                if item.stock_qty < entry['qty']:
                    raise ValueError(f"Insufficient stock for product: {item.name}")

                TransactionItem.objects.create(
                    transaction=txn,
                    item=item,
                    quantity=entry['qty'],
                    unit_price=item.selling_price
                )
                item.stock_qty -= entry['qty']
                item.save()

            return txn
```

**Key changes:**
- ✅ `Staff` model added for role-based staff management
- ✅ Cashier accounts created/managed via Django admin
- ✅ Transaction model updated: no `cashier` ForeignKey field

### 4. Inventory Views

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from .models import Item

class InventoryDashboardView(ListView):
    model = Item
    template_name = 'inventory/dashboard.html'
    context_object_name = 'inventory_items'

    def get_queryset(self):
        return Item.objects.filter(is_active=True).order_by('name')

class ItemCreateView(CreateView):
    model = Item
    fields = ['category', 'meal_subcategory', 'name', 'sku', 'emoji', 'image', 'cost_price',
              'selling_price', 'stock_qty', 'low_stock_threshold']
    template_name = 'inventory/item_form.html'
    success_url = reverse_lazy('inventory_dashboard')

class ItemUpdateView(UpdateView):
    model = Item
    fields = ['category', 'meal_subcategory', 'name', 'sku', 'emoji', 'image', 'cost_price',
              'selling_price', 'stock_qty', 'low_stock_threshold', 'is_active']
    template_name = 'inventory/item_form.html'
    success_url = reverse_lazy('inventory_dashboard')
```

**Key changes:**
- ✅ Added `emoji` and `image` fields to forms

### 5. POS Checkout API

```python
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import CheckoutEngine

@csrf_exempt
def checkout_submit_api(request):
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            cart = payload.get('cart', [])
            discount_id = payload.get('discount_id', None)
            pay_method = payload.get('payment_method', 'CASH')
            ref_num = payload.get('reference_number', None)
            diners = int(payload.get('total_diners', 1))
            specials = int(payload.get('special_count', 0))

            if not cart:
                return JsonResponse({'status': 'error', 'message': 'Cart empty'}, status=400)

            engine = CheckoutEngine(
                cart_data=cart,
                discount_id=discount_id,
                payment_method=pay_method,
                ref_num=ref_num,
                total_diners=diners,
                special_count=specials
            )

            executed_txn = engine.process()
            return JsonResponse({
                'status': 'success',
                'transaction_id': executed_txn.id,
                'grand_total': str(executed_txn.grand_total)
            })

        except ValueError as val_err:
            return JsonResponse({'status': 'error', 'message': str(val_err)}, status=400)
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Processing fault'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
```

**Key changes:**
- ✅ Staff user captured on checkout (future: link `Transaction` to `Staff`)
- ✅ Open endpoint — any active cashier can use it
- ✅ Admin `offline access` for management pages

### 5b. Product Catalog View — MealSubcategory Filtering

The `product_catalog` view at `/products/` renders a filterable grid of food items.
It supports optional `?subcategory=slug` query parameter to narrow by food group.

```python
def product_catalog(request):
    items = Item.objects.filter(is_active=True).select_related('meal_subcategory')
    subcategories = MealSubcategory.objects.all()
    current_subcategory = None

    subcategory_slug = request.GET.get("subcategory")
    if subcategory_slug:
        items = items.filter(meal_subcategory__slug=subcategory_slug)
        current_subcategory = subcategory_slug

    return render(request, "pos/products.html", {
        "items": items,
        "subcategories": subcategories,
        "current_subcategory": current_subcategory,
    })
```

The template renders a `<select>` dropdown filter at the top of the page.
Each item card optionally displays its `MealSubcategory` emoji + name.

**Seed data** (9 default groups): 🍗 Chicken, 🥩 Pork, 🥩 Beef, 🥦 Vegetables, 🍚 Rice, 🥤 Drinks, 🦐 Seafood, 🍜 Noodles, 🍰 Desserts.

### 6. POS Screen Template — Product Grid with Emoji/Image

The POS layout uses a 60/40 split: product grid on the left, checkout panel on the right. Each product card shows its emoji (or image) prominently for quick visual scanning — essential for fast-paced counter service.

```html
<!-- Product card — each item has emoji or image -->
<div class="product-card" onclick="addToCart({{ item.id }}, '{{ item.name }}', {{ item.selling_price }})">
    <div class="product-icon">{{ item.display_icon }}</div>
    {% if item.image %}
        <img src="{{ item.image.url }}" class="product-thumb" alt="{{ item.name }}">
    {% endif %}
    <h4>{{ item.name }}</h4>
    <p class="price">₱{{ item.selling_price|floatformat:2 }}</p>
    <small>Stock: {{ item.stock_qty }}</small>
</div>
```

### 7. Verification & Test Script

```bash
python manage.py shell
```

```python
from pos_app.models import Item, Category, DiscountType
from pos_app.services import CheckoutEngine

# Sample data
cat = Category.objects.create(name="Express Bulk Meals")
chicken = Item.objects.create(
    category=cat, name="8pc Chicken Meal Bundle", sku="CPM-08",
    emoji="🍗", cost_price=400.00, selling_price=650.00, stock_qty=50
)

# Add PH Senior/PWD discount
ph_law = DiscountType.objects.create(
    name="Senior / PWD", kind="PH_SPECIAL", value=20.00
)

# Test: 4 diners, 1 SC cardholder, 1 chicken bucket
engine = CheckoutEngine(
    cart_data=[{'item_id': chicken.id, 'qty': 1}],
    discount_id=ph_law.id,
    total_diners=4, special_count=1
)
txn = engine.process()

print(f"Subtotal: ₱{txn.subtotal}")
print(f"Discount: ₱{txn.discount_amount}")
print(f"Grand Total: ₱{txn.grand_total}")
# → ₱650.00 subtotal, ~₱30.86 discount, ~₱584.82 grand total
```

### Data Flow Summary

```
1. Admin creates staff accounts at /admin/ (login: username/password)
2. User opens Chrome Desktop App → localhost:8000
3. Sees product grid with emoji/images
4. Taps products to build cart
5. Applies discount (optional)
6. Hits Checkout → POST /pos/api/checkout/
7. CheckoutEngine validates stock, calculates VAT & discounts
8. Transaction + line items saved to SQLite
9. Stock deducted
10. Receipt displayed

Backup? Just copy db.sqlite3 — done.
```

### 8. Kitchen Order Ticket (KOT) Print

The KOT (Kitchen Order Ticket) endpoint at `GET /kot/<id>/print/` returns a printer-friendly
view of food preparation instructions — completely separate from the customer receipt.

**Differences from receipt:**
- No pricing, totals, or monetary amounts
- Table number prominently displayed (for dine-in)
- Clearly marked as "Food Preparation Copy"
- Shows order type (Dine-In/Take-Out) and order ID

**View:** `pos/views.kot_print` — decorated with `offline access`

**Template:** `pos/templates/pos/kot_print.html` — 80mm thermal receipt format

**Test coverage:** `KOTPrintTest` (10 tests) covering:
- URL resolution and 200 status
- No login required (offline mode)
- 404 for nonexistent transactions
- Display of table number, order type, item names + quantities
- Absence of pricing information
- Take-out orders show no table number
- Transaction/order ID display

### 9. Expense Tracking per Shift

Cashiers can record cash expenses during an open shift (e.g., “bought more ice,”
“paid tricycle delivery”). Expenses are linked to a shift for reconciliation.

**Model:** `Expense` in `pos/models.py`

| Field | Type | Description |
|-------|------|-------------|
| `shift` | ForeignKey (Shift) | Parent shift; related_name `expenses` |
| `amount` | DecimalField (max 10, 2) | Expense amount |
| `description` | CharField (255) | Description of the expense |
| `category` | CharField (100) | Optional category label (“Supplies,” “Delivery”) |
| `created_at` | DateTimeField | Auto-set on creation |

**API Endpoint:** `GET/POST /api/shifts/<shift_id>/expenses/`

- **GET** — Returns JSON list of expenses for the shift, ordered by newest first,
  plus a `total_expenses` sum
- **POST** — Create a new expense (requires `amount` and `description`, `category`
  optional)
- Requires authentication (`offline access`)

**Admin:** Registered as `ExpenseAdmin` at `/admin/pos/expense/` with filtering by
shift and category.

**Test coverage:** `ExpenseModelTest` (5 tests) + `ExpenseAPITest` (12 tests) —
17 total, all passing:
- Model field defaults, category optional, auto-set timestamps, string representation
- Shift-related expenses accessible via `shift.expenses` related name
- POST creates expense with full/minimal fields
- GET returns list with totals, empty shift returns empty list
- Validation: missing amount/description returns 400, invalid JSON returns 400
- No auth required (offline)
- 404 for non-existent shift
- Expense isolation between different shifts

### 10. Receipt Reprint & Void Watermark

The Sales History page (`/sales/`) includes a **Reprint button** (🖨️) for every transaction,
allowing cashiers to reprint a customer receipt on demand.

**How it works:**
- Each row in the sales table shows a 🖨️ link that opens `/receipt/<id>/print/`
- This reuses the existing `receipt_print` view — no new backend endpoint needed
- The receipt view is public (no `offline access`), but the sales history page is
  login-protected, so only authenticated staff can access the reprint links
- Also available per-row: a receipt link (🧾) for the regular receipt view

**Void watermark behavior:**
When a transaction is `VOIDED`, reprinted receipts include two visual indicators:
1. **Void watermark** — a large semi-transparent `VOID` text rotated -30° across the
   entire receipt, rendered via CSS `::before` pseudo-element on `.void-overlay`
2. **Void badge** — a prominent red-bordered "⛔ THIS RECEIPT IS VOIDED ⛔" banner at
   the top of the receipt

These indicators are purely CSS-based, ensuring compatibility with thermal printers
(80mm/58mm receipt paper) and working even with "Print" button or browser print.

**Test coverage:** `ReprintFromSalesHistoryTest` (5 tests) covering:
- Reprint link present for each transaction in sales history
- Reprint link resolves to the `receipt_print` URL
- Voided receipt shows VOID watermark text
- Voided receipt shows the "THIS RECEIPT IS VOIDED" badge
- Completed receipt does NOT show any void markers

### 11. End-of-Shift Reporting (X-Read / Z-Read)

Cashiers can generate shift reports via API endpoints that summarize sales, payments,
expenses, and cash reconciliation for a given shift.

**X-Read** — Interim report. Returns sales summary, payment breakdown, expenses, and
cash count info. Does **not** close the shift.

**Z-Read** — Final report. Returns the same data as X-Read, but **closes the shift**
(sets `status=CLOSED` and `end_time` to current time).

**API Endpoints:**

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/shifts/<shift_id>/x-read/` | Interim report (shift stays open) |
| `GET` | `/api/shifts/<shift_id>/z-read/` | Final report (closes the shift) |
| `GET` | `/api/shifts/<shift_id>/report/print/` | Printable HTML view (add `?type=xread` or `?type=zread`) |

**Report JSON structure:**

```json
{
  "shift_id": 1,
  "status": "OPEN" | "CLOSED",
  "start_time": "2026-06-22T09:00:00+00:00",
  "end_time": null | "2026-06-22T17:00:00+00:00",
  "starting_float": "1000.00",
  "total_sales": "1000.00",
  "net_sales": "920.00",
  "payment_breakdown": [
    {"method": "CASH", "total": "700.00", "count": 2},
    {"method": "DIGITAL", "total": "300.00", "count": 1}
  ],
  "total_expenses": "80.00",
  "expenses": [
    {"id": 1, "amount": "50.00", "description": "Ice", "category": "Supplies", "created_at": "..."}
  ],
  "total_counted": "1300.00",
  "expected_cash": "1620.00",
  "variance": "-320.00"
}
```

**Formulas:**
- `total_sales` = Sum of `grand_total` for COMPLETED transactions only (voided excluded)
- `net_sales` = `total_sales` - `total_expenses`
- `expected_cash` = `starting_float` + cash sales - expenses
- `variance` = `total_counted` - `expected_cash`

### 12. Clinic Remarks (Patient Chatbot Integration)

Clinic staff can add operational remarks/notes per patient record. These remarks are
stored in the `Patient` model's `remarks` text field (nullable) and can be edited via
the Django admin interface at `/admin/pos/patient/`.

**LLM Chatbot Integration:**
- `MessengerWebhookService` (in `pos/services.py`) provides `build_llm_context(patient)`
  to build a context string including the patient's clinic remarks.
- `build_system_prompt(patient)` constructs the full system prompt for the LLM with
  remark context injected when available.
- The system prompt instructs the LLM: explain clinic remarks naturally without
  revealing raw text verbatim unless the patient directly asks for the exact text.
- Empty/null remarks result in an empty context string (no remark info leaked).

**Restrictions:**
- Remarks are NEVER revealed verbatim to the patient — only LLM-interpreted natural answers.
- Only admin/superuser accounts can view/edit remarks via Django admin.

**Related Models:** `Patient` — name, fb_psid (unique), remarks, created_at, updated_at

**Test coverage:** `PatientModelTest` (5 tests) + `PatientAdminTest` (4 tests) + `MessengerWebhookServiceTest` (27 tests) = 36 total:
- Patient creation with/without remarks, string representation, updates and clearing
- Admin CRUD for patients including remarks field
- LLM context built with remarks included/excluded correctly
- Empty context for null patients or patients without remarks
- System prompt constructed with instructions to not reveal raw remarks
- PSID state classification (pre-registration / in-queue / post-queue)
- Pre-registration prompt includes clinic info (hours, address, services)
- Post-queue prompt includes last queue entry info and clinic remarks
- Routing logic for each state produces correct prompts

### 13. Queue Model & Clinic Queue Tracking

The `Queue` model (in `pos/models.py`) tracks clinic queue entries linked to a `Patient`.
Each entry records the service requested, clinic area, and current status.

```python
STATUS_CHOICES = [
    ("waiting", "Waiting"),
    ("served", "Served"),
    ("cancelled", "Cancelled"),
    ("skipped", "Skipped"),
]
```

**Fields:** patient (FK), status, service, service_area, notes, timestamps.
**Ordering:** newest first (-"created_at").
**Admin:** QueueAdmin at `/admin/pos/queue/` with status filter and patient search.

**Test coverage:** `QueueModelTest` (9 tests) — creation, all statuses, string rep, ordering, active scope.

### 14. Smart Unregistered Chat (LLM for Pre/Post Queue Users)

`MessengerWebhookService.classify_psid(psid)` classifies a Facebook PSID into one of
three states to determine how the chatbot responds:

| State | Condition | Prompt Used |
|-------|-----------|-------------|
| `preregistration` | PSID not linked to any Patient record | `build_preregistration_prompt()` — clinic info only (hours, address, services, FAQ) |
| `inqueue` | Patient has at least one Queue entry with status="waiting" | `build_system_prompt(patient)` — existing queue-aware prompt with remarks |
| `postqueue` | Patient exists but all Queue entries are served/cancelled/skipped | `build_postqueue_prompt(patient)` — last queue entry info + clinic remarks + clinic info |

**Pre-registration prompt** (`CLINIC_INFO`): Operating hours, address, contact info,
services offered, walk-in policy. No patient-specific data.

**Post-queue prompt** (`POSTQUEUE_CONTEXT_TEMPLATE`): Patient name, last queue entry
(status/service/area), clinic remarks, plus general clinic info. Designed for follow-up
questions about lab results, instructions, or next visit.

**DeepSeekService** (`pos/services.py`): Lightweight HTTP client using `urllib` (no
extra dependencies). Sends OpenAI-compatible chat completion requests to DeepSeek API.
Configurable via environment variables:
- `DEEPSEEK_API_KEY` (required)
- `DEEPSEEK_API_URL` (default: https://api.deepseek.com/v1/chat/completions)
- `DEEPSEEK_MODEL` (default: deepseek-chat)

**Orchestration:** `get_response_for_psid(psid, user_message)` classifies the PSID,
selects the correct prompt builder, and sends the message to DeepSeek.

**Test coverage:** `MessengerWebhookServiceTest` (18 new tests) — state classification,
prompt content checks (clinic info, queue info, remarks), prompt differences between
states, routing logic.

**Test coverage:** `ShiftXReadTest` (12 tests) + `ShiftZReadTest` (9 tests) = 21 total:
- X-Read returns 200, expected keys, correct totals, payment breakdown, expenses list
- X-Read expected cash and variance calculations
- X-Read does NOT close the shift
- X-Read handles empty shifts (zeros), non-existent shifts (404), auth requirement
- Z-Read returns 200, closes shift, correct values after close
- Z-Read on already-closed shift returns 409
- Z-Read with no cash count returns zeros
- Z-Read renders X-Read still usable on closed shifts
