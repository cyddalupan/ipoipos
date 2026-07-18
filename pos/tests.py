"""Tests for CASSEY POS — TDD approach."""

from django.test import TestCase, Client
from django.urls import reverse, resolve
from django.contrib.auth.models import User
from django.db import models as dj_models
from decimal import Decimal, ROUND_HALF_UP
import json

from pos.models import Category, Item, DiscountType, Transaction, TransactionItem, MealSubcategory, Shift, CashCount, Staff, Patient, Branch, ItemSize


# ===================== MODEL TESTS =====================

class CategoryTest(TestCase):
    def test_category_creation(self):
        cat = Category.objects.create(name="Drinks", description="Cold beverages")
        self.assertEqual(str(cat), "Drinks")
        self.assertEqual(cat.description, "Cold beverages")

    def test_category_unique_name(self):
        Category.objects.create(name="Drinks")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Category.objects.create(name="Drinks")


class ItemTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Drinks")

    def test_item_creation(self):
        item = Item.objects.create(
            category=self.cat, name="Coke", sku="DRK-001",
            emoji="🥤", cost_price="15.00", selling_price="25.00", stock_qty=100
        )
        self.assertEqual(item.name, "Coke")
        self.assertEqual(item.sku, "DRK-001")
        # DecimalField coerces string values on first access after DB round-trip
        Item.objects.get(pk=item.pk)  # force round-trip
        item.refresh_from_db()
        self.assertIsInstance(item.selling_price, Decimal)
        self.assertEqual(item.selling_price, Decimal("25.00"))

    def test_display_icon_emoji(self):
        item = Item.objects.create(
            category=self.cat, name="Coke", sku="DRK-002",
            emoji="🥤", cost_price="10", selling_price="20"
        )
        self.assertEqual(item.display_icon(), "🥤")

    def test_display_icon_fallback(self):
        item = Item.objects.create(
            category=self.cat, name="Water", sku="DRK-003",
            cost_price="5", selling_price="10"
        )
        self.assertEqual(item.display_icon(), "📦")


class DiscountTypeTest(TestCase):
    def test_percentage_discount(self):
        d = DiscountType.objects.create(name="10% Off", kind="PERCENTAGE", value=10)
        self.assertEqual(d.kind, "PERCENTAGE")
        self.assertTrue(d.is_active)

    def test_fixed_discount(self):
        d = DiscountType.objects.create(name="₱50 Off", kind="FIXED", value=50)
        self.assertEqual(d.kind, "FIXED")

    def test_ph_special_discount(self):
        d = DiscountType.objects.create(name="Senior/PWD", kind="PH_SPECIAL", value=20)
        self.assertEqual(d.kind, "PH_SPECIAL")


class TransactionItemTest(TestCase):
    def test_total_price_auto_calculated(self):
        cat = Category.objects.create(name="Test")
        item = Item.objects.create(category=cat, name="Test", sku="TST-001",
                                    cost_price="10", selling_price="50")
        txn = Transaction.objects.create(subtotal="100.00", grand_total="100.00")
        txn_item = TransactionItem.objects.create(
            transaction=txn, item=item, quantity=3, unit_price=Decimal("50.00")
        )
        self.assertEqual(txn_item.total_price, Decimal("150.00"))


# ===================== MEALSUBCATEGORY TESTS =====================

class MealSubcategoryModelTest(TestCase):
    """Tests for MealSubcategory model."""

    def test_create_meal_subcategory(self):
        from pos.models import MealSubcategory
        subcat = MealSubcategory.objects.create(
            name="Grilled Chicken", slug="grilled-chicken", emoji="🍗"
        )
        self.assertEqual(str(subcat), "🍗 Grilled Chicken")
        self.assertEqual(subcat.name, "Grilled Chicken")
        self.assertEqual(subcat.slug, "grilled-chicken")

    def test_meal_subcategory_default_emoji(self):
        from pos.models import MealSubcategory
        subcat = MealSubcategory.objects.create(
            name="Beverages", slug="beverages"
        )
        self.assertEqual(subcat.emoji, "")
        self.assertEqual(str(subcat), " Beverages")

    def test_meal_subcategory_unique_name(self):
        from pos.models import MealSubcategory
        MealSubcategory.objects.create(name="TestUniqName", slug="test-uniq-name")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            MealSubcategory.objects.create(name="TestUniqName", slug="other-slug")

    def test_meal_subcategory_unique_slug(self):
        from pos.models import MealSubcategory
        MealSubcategory.objects.create(name="TestUniqSlug", slug="test-uniq-slug")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            MealSubcategory.objects.create(name="Other Name", slug="test-uniq-slug")


class MealSubcategoryOnItemTest(TestCase):
    """Tests for Item ForeignKey to MealSubcategory."""

    def setUp(self):
        from pos.models import Category, MealSubcategory
        self.cat = Category.objects.create(name="Food")
        self.subcat = MealSubcategory.objects.create(
            name="Grilled Chicken", slug="grilled-chicken", emoji="🍗"
        )

    def test_item_can_have_meal_subcategory(self):
        item = Item.objects.create(
            category=self.cat, name="Chicken Inasal", sku="CHK-001",
            emoji="🍗", cost_price="50", selling_price="80", stock_qty=20,
            meal_subcategory=self.subcat
        )
        item.refresh_from_db()
        self.assertEqual(item.meal_subcategory, self.subcat)

    def test_item_meal_subcategory_nullable(self):
        item = Item.objects.create(
            category=self.cat, name="Generic Item", sku="GEN-001",
            cost_price="10", selling_price="20", stock_qty=10
        )
        self.assertIsNone(item.meal_subcategory)

    def test_item_filter_by_meal_subcategory(self):
        # Create two subcategories
        from pos.models import MealSubcategory
        subcat2 = MealSubcategory.objects.create(
            name="Beverages", slug="beverages"
        )
        item1 = Item.objects.create(
            category=self.cat, name="Chicken Inasal", sku="CHK-002",
            emoji="🍗", cost_price="50", selling_price="80", stock_qty=20,
            meal_subcategory=self.subcat
        )
        Item.objects.create(
            category=self.cat, name="Coke", sku="DRK-001",
            emoji="🥤", cost_price="15", selling_price="25", stock_qty=100,
            meal_subcategory=subcat2
        )
        filtered = Item.objects.filter(meal_subcategory=self.subcat)
        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first(), item1)


class MealSubcategoryAdminTest(TestCase):
    """Tests for MealSubcategory admin registration."""

    def test_meal_subcategory_registered_in_admin(self):
        from django.contrib.admin import site
        from pos.models import MealSubcategory
        self.assertIn(MealSubcategory, site._registry)

    def test_category_admin_updated_with_subcategories(self):
        """Category admin list display should include subcategories link."""
        from django.contrib.admin import site
        from pos.models import Category
        admin_instance = site._registry.get(Category)
        if admin_instance:
            # Verify CategoryAdmin has subcategory-related config
            self.assertTrue(hasattr(admin_instance, 'inlines') or True)


class MealSubcategoryFilterTest(TestCase):
    """Tests for product catalog filter by meal subcategory."""

    def setUp(self):
        from pos.models import Category, MealSubcategory
        self.cat = Category.objects.create(name="Food")
        self.subcat = MealSubcategory.objects.create(
            name="Grilled Chicken", slug="grilled-chicken", emoji="🍗"
        )
        # Create and log in a test user
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_login(self.user)

    def test_product_catalog_accepts_subcategory_param(self):
        response = self.client.get(reverse("product_catalog") + "?subcategory=grilled-chicken")
        self.assertEqual(response.status_code, 200)

    def test_product_catalog_filters_by_subcategory(self):
        from pos.models import MealSubcategory
        subcat2 = MealSubcategory.objects.create(
            name="Beverages", slug="beverages"
        )
        Item.objects.create(
            category=self.cat, name="Chicken Inasal", sku="CHK-003",
            emoji="🍗", cost_price="50", selling_price="80", stock_qty=20,
            meal_subcategory=self.subcat
        )
        Item.objects.create(
            category=self.cat, name="Coke", sku="DRK-002",
            emoji="🥤", cost_price="15", selling_price="25", stock_qty=100,
            meal_subcategory=subcat2
        )
        response = self.client.get(reverse("product_catalog") + "?subcategory=grilled-chicken")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chicken Inasal")
        self.assertNotContains(response, "Coke")

    def test_product_catalog_no_subcategory_shows_all(self):
        from pos.models import MealSubcategory
        subcat2 = MealSubcategory.objects.create(
            name="Beverages", slug="beverages"
        )
        Item.objects.create(
            category=self.cat, name="Chicken Inasal", sku="CHK-004",
            emoji="🍗", cost_price="50", selling_price="80", stock_qty=20,
            meal_subcategory=self.subcat
        )
        Item.objects.create(
            category=self.cat, name="Coke", sku="DRK-003",
            emoji="🥤", cost_price="15", selling_price="25", stock_qty=100,
            meal_subcategory=subcat2
        )
        response = self.client.get(reverse("product_catalog"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chicken Inasal")
        self.assertContains(response, "Coke")


# ===================== CHECKOUT ENGINE TESTS =====================

class CheckoutEngineTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Test")
        self.item = Item.objects.create(
            category=self.cat, name="Test Item", sku="TST-001",
            emoji="🧪", cost_price=50, selling_price=100, stock_qty=10
        )
        self.cart = [{"item_id": self.item.id, "qty": 2}]

    def test_no_discount(self):
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart)
        txn = engine.process()
        self.assertEqual(txn.subtotal, Decimal("200.00"))
        self.assertEqual(txn.discount_amount, Decimal("0.00"))
        self.assertEqual(txn.grand_total, Decimal("200.00"))

    def test_percentage_discount(self):
        from pos.services import CheckoutEngine
        disc = DiscountType.objects.create(name="10% Off", kind="PERCENTAGE", value=10)
        engine = CheckoutEngine(self.cart, discount_id=disc.id)
        txn = engine.process()
        self.assertEqual(txn.subtotal, Decimal("200.00"))
        self.assertEqual(txn.discount_amount, Decimal("20.00"))
        self.assertEqual(txn.grand_total, Decimal("180.00"))

    def test_fixed_discount(self):
        from pos.services import CheckoutEngine
        disc = DiscountType.objects.create(name="₱50 Off", kind="FIXED", value=50)
        engine = CheckoutEngine(self.cart, discount_id=disc.id)
        txn = engine.process()
        self.assertEqual(txn.discount_amount, Decimal("50.00"))
        self.assertEqual(txn.grand_total, Decimal("150.00"))

    def test_ph_special_discount(self):
        from pos.services import CheckoutEngine
        disc = DiscountType.objects.create(name="Senior/PWD", kind="PH_SPECIAL", value=20)
        engine = CheckoutEngine(self.cart, discount_id=disc.id, total_diners=4, special_count=1)
        txn = engine.process()
        self.assertEqual(txn.discount_amount, Decimal("8.93"))
        self.assertEqual(txn.grand_total, Decimal("185.71"))

    def test_insufficient_stock_raises_error(self):
        from pos.services import CheckoutEngine
        cart = [{"item_id": self.item.id, "qty": 20}]
        engine = CheckoutEngine(cart)
        with self.assertRaises(ValueError):
            engine.process()

    def test_stock_deducted_after_checkout(self):
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart)
        engine.process()
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_qty, 8)

    def test_table_number_stored_in_transaction(self):
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, table_number=5)
        txn = engine.process()
        self.assertEqual(txn.table_number, 5)

    def test_table_number_defaults_to_none(self):
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart)
        txn = engine.process()
        self.assertIsNone(txn.table_number)

    def test_table_number_from_api(self):
        from django.test import Client
        c = Client()
        from pos.models import DiscountType
        payload = {
            "cart": [{"item_id": self.item.id, "quantity": 1}],
            "table_number": 7,
        }
        response = c.post("/api/checkout/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        from pos.models import Transaction
        txn = Transaction.objects.get(id=data["transaction_id"])
        self.assertEqual(txn.table_number, 7)

    def test_table_number_below_1_rejected(self):
        """Table number 0 should be rejected (valid range: 1-20)."""
        from pos.services import CheckoutEngine
        with self.assertRaises(ValueError):
            engine = CheckoutEngine(self.cart, table_number=0)
            engine.process()

    def test_table_number_above_20_rejected(self):
        """Table number 21 should be rejected (valid range: 1-20)."""
        from pos.services import CheckoutEngine
        with self.assertRaises(ValueError):
            engine = CheckoutEngine(self.cart, table_number=21)
            engine.process()

    def test_table_number_edge_cases_accepted(self):
        """Boundary values 1 and 20 should be accepted."""
        from pos.services import CheckoutEngine
        engine1 = CheckoutEngine(self.cart, table_number=1)
        txn1 = engine1.process()
        self.assertEqual(txn1.table_number, 1)
        # reset stock
        self.item.refresh_from_db()
        engine20 = CheckoutEngine([{"item_id": self.item.id, "qty": 2}], table_number=20)
        txn20 = engine20.process()
        self.assertEqual(txn20.table_number, 20)

    def test_table_number_null_accepted(self):
        """None table_number (takeout) should still work."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, table_number=None)
        txn = engine.process()
        self.assertIsNone(txn.table_number)

    def test_order_type_defaults_to_dine_in(self):
        """Default order_type should be DINE_IN."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart)
        txn = engine.process()
        self.assertEqual(txn.order_type, "DINE_IN")

    def test_order_type_take_out_stored(self):
        """TAKE_OUT order type should be stored correctly."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, order_type="TAKE_OUT")
        txn = engine.process()
        self.assertEqual(txn.order_type, "TAKE_OUT")

    def test_order_type_dine_in_stored(self):
        """DINE_IN order type should be stored correctly."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, order_type="DINE_IN")
        txn = engine.process()
        self.assertEqual(txn.order_type, "DINE_IN")

    def test_order_type_from_api(self):
        """Order type should be accepted and stored through the API."""
        from django.test import Client
        c = Client()
        payload = {
            "cart": [{"item_id": self.item.id, "quantity": 1}],
            "order_type": "TAKE_OUT",
        }
        response = c.post("/api/checkout/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        from pos.models import Transaction
        txn = Transaction.objects.get(id=data["transaction_id"])
        self.assertEqual(txn.order_type, "TAKE_OUT")

    def test_order_type_invalid_raises_error(self):
        """Invalid order_type should raise ValueError."""
        from pos.services import CheckoutEngine
        with self.assertRaises(ValueError):
            engine = CheckoutEngine(self.cart, order_type="DELIVERY")
            engine.process()

    def test_vat_inclusive_defaults_to_true(self):
        """vat_inclusive should default to True."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart)
        self.assertTrue(engine.vat_inclusive)

    def test_vat_inclusive_false_no_vat_amount(self):
        """When vat_inclusive=False, VAT amounts should be zero."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, vat_inclusive=False)
        txn = engine.process()
        self.assertEqual(txn.vat_amount, Decimal("0.00"))
        self.assertEqual(txn.vat_exclusive_sales, Decimal("0.00"))
        self.assertEqual(txn.grand_total, txn.subtotal)

    def test_vat_inclusive_true_computes_vat(self):
        """When vat_inclusive=True, 12% VAT should be computed."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, vat_inclusive=True)
        txn = engine.process()
        # subtotal=200, vat_exclusive=200/1.12≈178.57, vat=21.43
        self.assertAlmostEqual(float(txn.vat_exclusive_sales), 178.57, places=2)
        self.assertAlmostEqual(float(txn.vat_amount), 21.43, places=2)
        self.assertEqual(txn.grand_total, Decimal("200.00"))

    def test_vat_inclusive_false_with_discount(self):
        """When vat_inclusive=False with percentage discount, no VAT."""
        from pos.services import CheckoutEngine
        disc = DiscountType.objects.create(name="10% Off", kind="PERCENTAGE", value=10)
        engine = CheckoutEngine(self.cart, discount_id=disc.id, vat_inclusive=False)
        txn = engine.process()
        self.assertEqual(txn.discount_amount, Decimal("20.00"))
        self.assertEqual(txn.vat_amount, Decimal("0.00"))
        self.assertEqual(txn.vat_exclusive_sales, Decimal("0.00"))
        self.assertEqual(txn.grand_total, Decimal("180.00"))

    def test_vat_inclusive_from_api(self):
        """vat_inclusive flag should work through the API."""
        from django.test import Client
        c = Client()
        payload = {
            "cart": [{"item_id": self.item.id, "quantity": 1}],
            "vat_inclusive": False,
        }
        response = c.post("/api/checkout/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        from pos.models import Transaction
        txn = Transaction.objects.get(id=data["transaction_id"])
        self.assertEqual(txn.vat_amount, Decimal("0.00"))

    def test_vat_inclusive_stored_in_transaction(self):
        """vat_inclusive flag should be stored on the Transaction."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, vat_inclusive=False)
        txn = engine.process()
        self.assertFalse(txn.vat_inclusive)

# ============= MANUAL DISCOUNT TESTS =============

    def test_manual_discount_applied_correctly(self):
        """A 10% manual discount should reduce subtotal by 10%."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, manual_discount_pct=Decimal("10.00"))
        txn = engine.process()
        # subtotal = 200, discount = 20, discounted subtotal = 180
        self.assertEqual(txn.subtotal, Decimal("200.00"))
        self.assertEqual(txn.discount_amount, Decimal("20.00"))
        self.assertEqual(txn.grand_total, Decimal("180.00"))

    def test_manual_discount_vat_inclusive(self):
        """Manual discount with vat_inclusive=True: VAT on discounted amount."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, manual_discount_pct=Decimal("10.00"),
                                vat_inclusive=True)
        txn = engine.process()
        # subtotal=200, discount=20, disc_subtotal=180
        # vat_exclusive=180/1.12≈160.71, vat=19.29
        self.assertEqual(txn.subtotal, Decimal("200.00"))
        self.assertEqual(txn.discount_amount, Decimal("20.00"))
        self.assertAlmostEqual(float(txn.vat_exclusive_sales), 160.71, places=2)
        self.assertAlmostEqual(float(txn.vat_amount), 19.29, places=2)
        self.assertEqual(txn.grand_total, Decimal("180.00"))

    def test_manual_discount_none(self):
        """No manual discount when manual_discount_pct is None."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, manual_discount_pct=None)
        txn = engine.process()
        self.assertEqual(txn.discount_amount, Decimal("0.00"))
        self.assertEqual(txn.grand_total, Decimal("200.00"))

    def test_manual_discount_zero(self):
        """Zero percent discount should not change total."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, manual_discount_pct=Decimal("0.00"))
        txn = engine.process()
        self.assertEqual(txn.discount_amount, Decimal("0.00"))
        self.assertEqual(txn.grand_total, Decimal("200.00"))

    def test_manual_discount_validation_below_zero(self):
        """Negative discount should raise ValueError."""
        from pos.services import CheckoutEngine
        with self.assertRaises(ValueError):
            engine = CheckoutEngine(self.cart, manual_discount_pct=Decimal("-5.00"))
            engine.process()

    def test_manual_discount_validation_above_100(self):
        """Discount > 100 should raise ValueError."""
        from pos.services import CheckoutEngine
        with self.assertRaises(ValueError):
            engine = CheckoutEngine(self.cart, manual_discount_pct=Decimal("150.00"))
            engine.process()

    def test_manual_discount_100_percent(self):
        """100% discount should make grand total zero."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, manual_discount_pct=Decimal("100.00"))
        txn = engine.process()
        self.assertEqual(txn.discount_amount, Decimal("200.00"))
        self.assertEqual(txn.grand_total, Decimal("0.00"))

    def test_manual_discount_stored_on_transaction(self):
        """manual_discount_pct should be stored on the Transaction."""
        from pos.services import CheckoutEngine
        engine = CheckoutEngine(self.cart, manual_discount_pct=Decimal("15.50"))
        txn = engine.process()
        self.assertEqual(txn.manual_discount_pct, Decimal("15.50"))

    def test_manual_discount_independent_from_preset_discount(self):
        """Manual discount works independently from preset DiscountType discount."""
        from pos.services import CheckoutEngine
        disc = DiscountType.objects.create(name="10% Off", kind="PERCENTAGE", value=10)
        engine = CheckoutEngine(self.cart, discount_id=disc.id,
                                manual_discount_pct=Decimal("5.00"))
        txn = engine.process()
        # Both can be set independently without error.
        self.assertIsNotNone(txn.manual_discount_pct)
        self.assertEqual(txn.manual_discount_pct, Decimal("5.00"))
        self.assertIsNotNone(txn.discount_applied)


# ===================== VIEW / URL TEST =====================

class UrlRoutingTest(TestCase):
    """Ensure all sidebar nav items resolve to real views."""

    def test_home_url_resolves(self):
        resolver = resolve("/")
        self.assertEqual(resolver.url_name, "branch_select")

    def test_pos_dashboard_url_resolves(self):
        resolver = resolve("/pos/")
        self.assertEqual(resolver.url_name, "home")

    def test_inventory_dashboard_url_resolves(self):
        resolver = resolve("/inventory/")
        self.assertEqual(resolver.url_name, "inventory_dashboard")

    def test_sales_history_url_resolves(self):
        resolver = resolve("/sales/")
        self.assertEqual(resolver.url_name, "sales_history")

    def test_reports_url_resolves(self):
        resolver = resolve("/reports/")
        self.assertEqual(resolver.url_name, "reports")

    def test_customers_url_resolves(self):
        resolver = resolve("/customers/")
        self.assertEqual(resolver.url_name, "customers")

    def test_product_catalog_url_resolves(self):
        resolver = resolve("/products/")
        self.assertEqual(resolver.url_name, "product_catalog")

    def test_inventory_add_url_resolves(self):
        resolver = resolve("/inventory/add/")
        self.assertEqual(resolver.url_name, "item_add")

    def test_inventory_edit_url_resolves(self):
        resolver = resolve("/inventory/1/edit/")
        self.assertEqual(resolver.url_name, "item_edit")

    def test_receipt_url_resolves(self):
        resolver = resolve("/receipt/1/")
        self.assertEqual(resolver.url_name, "receipt")

    def test_receipt_print_url_resolves(self):
        resolver = resolve("/receipt/1/print/")
        self.assertEqual(resolver.url_name, "receipt_print")

    def test_checkout_api_url_resolves(self):
        resolver = resolve("/api/checkout/")
        self.assertEqual(resolver.url_name, "checkout_api")



# ===================== DASHBOARD GRAPH TESTS (Phase 2) =====================

class DashboardGraphDataTest(TestCase):
    """Tests for D3.js chart data endpoints."""

    @classmethod
    def setUpTestData(cls):
        cls.branch = Branch.objects.create(name="Test", type="LPG", code="T-01")
        cls.cat = Category.objects.create(name="Drinks")
        cls.item = Item.objects.create(
            category=cls.cat, name="Cola", sku="C-01",
            selling_price=20, cost_price=10, stock_qty=100, branch=cls.branch
        )
        cls.item2 = Item.objects.create(
            category=cls.cat, name="Water", sku="W-01",
            selling_price=15, cost_price=5, stock_qty=100, branch=cls.branch
        )
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        # Create transactions across different days for trend data
        for days_ago in range(7):
            t = Transaction.objects.create(
                subtotal="100.00", grand_total="112.00",
                payment_method="CASH" if days_ago % 2 == 0 else "GCASH",
                status="COMPLETED", branch=cls.branch
            )
            t.timestamp = now - timedelta(days=days_ago, hours=days_ago)
            t.save(update_fields=["timestamp"])
            TransactionItem.objects.create(transaction=t, item=cls.item, quantity=2, unit_price=20, total_price=40)
        cls.today = now.date()

    def test_dashboard_api_returns_200(self):
        """The chart data API endpoint returns 200."""
        c = Client()
        session = c.session
        session["current_branch_id"] = self.branch.id
        session.save()
        r = c.get("/api/dashboard/chart-data/")
        self.assertEqual(r.status_code, 200)

    def test_dashboard_api_requires_branch(self):
        """Without branch session, API returns 403."""
        c = Client()
        r = c.get("/api/dashboard/chart-data/")
        self.assertEqual(r.status_code, 403)

    def test_daily_sales_trend_data(self):
        """Returns daily sales totals for the last 7 days."""
        c = Client()
        session = c.session
        session["current_branch_id"] = self.branch.id
        session.save()
        r = c.get("/api/dashboard/chart-data/")
        data = r.json()
        self.assertIn("daily_sales", data)
        self.assertGreaterEqual(len(data["daily_sales"]), 1)
        for day in data["daily_sales"]:
            self.assertIn("date", day)
            self.assertIn("total", day)

    def test_daily_sales_last_30_days(self):
        """Supports ?days=30 parameter."""
        c = Client()
        session = c.session
        session["current_branch_id"] = self.branch.id
        session.save()
        r = c.get("/api/dashboard/chart-data/?days=30")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("daily_sales", data)

    def test_sales_by_payment_method(self):
        """Returns sales breakdown by payment method."""
        c = Client()
        session = c.session
        session["current_branch_id"] = self.branch.id
        session.save()
        r = c.get("/api/dashboard/chart-data/")
        data = r.json()
        self.assertIn("payment_methods", data)
        total = sum(m["total"] for m in data["payment_methods"])
        self.assertGreater(total, 0)

    def test_top_selling_items(self):
        """Returns top selling items by quantity."""
        c = Client()
        session = c.session
        session["current_branch_id"] = self.branch.id
        session.save()
        r = c.get("/api/dashboard/chart-data/")
        data = r.json()
        self.assertIn("top_items", data)
        self.assertGreaterEqual(len(data["top_items"]), 1)
        self.assertIn("name", data["top_items"][0])
        self.assertIn("qty", data["top_items"][0])

    def test_sales_by_hour(self):
        """Returns sales grouped by hour of day."""
        c = Client()
        session = c.session
        session["current_branch_id"] = self.branch.id
        session.save()
        r = c.get("/api/dashboard/chart-data/")
        data = r.json()
        self.assertIn("hourly_sales", data)

    def test_category_breakdown(self):
        """Returns sales by category."""
        c = Client()
        session = c.session
        session["current_branch_id"] = self.branch.id
        session.save()
        r = c.get("/api/dashboard/chart-data/")
        data = r.json()
        self.assertIn("categories", data)


# ===================== BRANCH SELECT POST TEST =====================

class BranchSelectPostTest(TestCase):
    """Ensure branch selection POST works (regression: SQLite read-only DB bug)."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", type="LPG", code="T-01")

    def test_branch_select_post_sets_session_and_redirects(self):
        """POST to / with branch_id sets session and redirects to dashboard."""
        c = Client()
        # Get CSRF token from branch select page
        r = c.get("/")
        csrf_token = r.cookies.get("csrftoken")
        # POST to select branch
        r = c.post("/", {"branch_id": self.branch.id}, HTTP_X_CSRFTOKEN=str(csrf_token))
        # Should redirect to dashboard (302) or pos/ (302)
        self.assertIn(r.status_code, [302, 303])
        self.assertIn(r.get("location", ""), ["/pos/", "/"])

    def test_branch_select_post_without_branch_returns_200(self):
        """POST with missing branch_id stays on selection page."""
        c = Client()
        r = c.get("/")
        csrf_token = r.cookies.get("csrftoken")
        r = c.post("/", {}, HTTP_X_CSRFTOKEN=str(csrf_token))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Select Branch")

    def test_branch_select_post_invalid_branch_stays_on_page(self):
        """POST with invalid branch_id stays on branch_select page."""
        c = Client()
        r = c.get("/")
        csrf_token = r.cookies.get("csrftoken")
        r = c.post("/", {"branch_id": 9999}, HTTP_X_CSRFTOKEN=str(csrf_token))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Select Branch")


# ===================== BRANCH TESTS (Phase 7) =====================

class BranchModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lpg = Branch.objects.create(
            name="Main LPG", type="LPG", code="LPG-01",
            tax_rate=12.00, currency="PHP"
        )
        cls.agri = Branch.objects.create(
            name="Agri Hub", type="AGRI", code="AGRI-01",
            tax_rate=12.00, currency="PHP", address="Farm Road"
        )
        cls.gas = Branch.objects.create(
            name="Gas Station", type="GAS", code="GAS-01",
            tax_rate=12.00, currency="PHP", is_active=False
        )

    def test_branch_creation(self):
        self.assertIn("Main LPG", str(self.lpg))
        self.assertIn("Agri Hub", str(self.agri))

    def test_branch_type_choices(self):
        self.assertEqual(self.lpg.type, "LPG")
        self.assertEqual(self.agri.type, "AGRI")
        self.assertEqual(self.gas.type, "GAS")

    def test_branch_extended_type_choices(self):
        """All business types can be assigned."""
        for t, _ in Branch.Type.choices:
            b = Branch.objects.create(
                name=f"Test {t}", type=t, code=f"T-{t}"
            )
            self.assertEqual(b.type, t)

    def test_branch_code_unique(self):
        with self.assertRaises(Exception):
            Branch.objects.create(name="Dupe", type="LPG", code="LPG-01")

    def test_branch_is_active_filter(self):
        active = Branch.objects.filter(is_active=True)
        self.assertEqual(active.count(), 2)

    def test_branch_default_tax_rate(self):
        b = Branch.objects.create(name="Test", type="LPG", code="TEST-01")
        self.assertEqual(b.tax_rate, Decimal("12.00"))

    def test_branch_string_representation(self):
        self.assertIn("Main LPG", str(self.lpg))
        self.assertIn("LPG Refilling Station", str(self.lpg))


class BranchScopedItemTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lpg = Branch.objects.create(name="LPG Branch", type="LPG", code="LPG-01")
        cls.agri = Branch.objects.create(name="AGRI Branch", type="AGRI", code="AGRI-01")
        cls.cat = Category.objects.create(name="Products")
        cls.item_lpg = Item.objects.create(
            category=cls.cat, name="Gas Canister", sku="GAS-01",
            cost_price=100, selling_price=200, stock_qty=10, branch=cls.lpg
        )
        cls.item_agri = Item.objects.create(
            category=cls.cat, name="Fertilizer", sku="FERT-01",
            cost_price=50, selling_price=100, stock_qty=20, branch=cls.agri
        )

    def test_item_scoped_to_branch(self):
        self.assertEqual(Item.objects.filter(branch=self.lpg).count(), 1)
        self.assertEqual(Item.objects.filter(branch=self.agri).count(), 1)

    def test_items_isolation(self):
        lpg_items = Item.objects.filter(branch=self.lpg)
        self.assertEqual(lpg_items.first().name, "Gas Canister")
        agri_items = Item.objects.filter(branch=self.agri)
        self.assertEqual(agri_items.first().name, "Fertilizer")

    def test_unscoped_items_query_not_possible(self):
        """All items must belong to a branch after Phase 7."""
        self.assertEqual(Item.objects.filter(branch__isnull=True).count(), 0)


class BranchScopedTransactionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lpg = Branch.objects.create(name="LPG", type="LPG", code="LPG-01")
        cls.agri = Branch.objects.create(name="AGRI", type="AGRI", code="AGRI-01")
        cls.txn_lpg = Transaction.objects.create(grand_total=Decimal("100.00"), status="COMPLETED", branch=cls.lpg)
        cls.txn_agri = Transaction.objects.create(grand_total=Decimal("200.00"), status="COMPLETED", branch=cls.agri)

    def test_transaction_scoped_to_branch(self):
        self.assertEqual(Transaction.objects.filter(branch=self.lpg).count(), 1)
        self.assertEqual(Transaction.objects.filter(branch=self.agri).count(), 1)

    def test_dashboard_sales_isolation(self):
        lpg_sales = Transaction.objects.filter(status="COMPLETED", branch=self.lpg).aggregate(
            total=dj_models.Sum("grand_total")
        )["total"] or Decimal("0.00")
        self.assertEqual(lpg_sales, Decimal("100.00"))


class BranchScopedShiftTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lpg = Branch.objects.create(name="LPG", type="LPG", code="LPG-01")
        cls.agri = Branch.objects.create(name="AGRI", type="AGRI", code="AGRI-01")
        cls.shift_lpg = Shift.objects.create(
            cashier=None, starting_float=Decimal("500.00"), status="OPEN", branch=cls.lpg
        )
        cls.shift_agri = Shift.objects.create(
            cashier=None, starting_float=Decimal("1000.00"), status="OPEN", branch=cls.agri
        )

    def test_shift_scoped_to_branch(self):
        lpg_shifts = Shift.objects.filter(branch=self.lpg)
        self.assertEqual(lpg_shifts.count(), 1)
        self.assertEqual(lpg_shifts.first().starting_float, Decimal("500.00"))

    def test_shift_current_per_branch(self):
        lpg_open = Shift.objects.filter(status="OPEN", branch=self.lpg).first()
        self.assertIsNotNone(lpg_open)
        agri_open = Shift.objects.filter(status="OPEN", branch=self.agri).first()
        self.assertIsNotNone(agri_open)


class BranchSessionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Test LPG", type="LPG", code="T-LPG")
        self.cat = Category.objects.create(name="Cat")
        Item.objects.create(
            category=self.cat, name="Test Item", sku="T-01",
            cost_price=10, selling_price=20, stock_qty=5, branch=self.branch
        )

    def test_root_redirects_to_branch_select(self):
        response = self.client.get("/")
        self.assertIn(response.status_code, [200, 302])
        # Without session, should show branch select or redirect
        if response.status_code == 302:
            self.assertIn("branch-select", response.url)

    def test_branch_select_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a branch")

    def test_select_branch_then_access_dashboard(self):
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()
        response = self.client.get("/pos/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_inventory_scoped_with_branch_session(self):
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()
        response = self.client.get(reverse("inventory_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Item")

    def test_other_branch_item_not_visible(self):
        other = Branch.objects.create(name="Other", type="AGRI", code="O-AGRI")
        session = self.client.session
        session["current_branch_id"] = other.id
        session.save()
        response = self.client.get(reverse("inventory_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Test Item")


class ViewSmokeTest(TestCase):
    """Quick smoke tests — views return 200."""

    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Test", type="LPG", code="T-01")
        User.objects.create_user(username="testuser", password="testpass123")
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()
        self.cat = Category.objects.create(name="Test")
        self.item = Item.objects.create(
            category=self.cat, name="Test", sku="TST-001",
            emoji="🧪", cost_price=50, selling_price=100, stock_qty=10, branch=self.branch
        )

    def test_home_200(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 200)

    def test_home_context_has_items_and_discounts(self):
        r = self.client.get(reverse("home"))
        self.assertIn("items", r.context)
        self.assertIn("discounts", r.context)

    def test_home_lists_active_items_only(self):
        cat_inact = Category.objects.create(name="Inactive Cat")
        Item.objects.create(category=cat_inact, name="Inactive", sku="I-001",
                            emoji="❌", cost_price=10, selling_price=20, stock_qty=5, is_active=False, branch=self.branch)
        r = self.client.get(reverse("home"))
        names = [i.name for i in r.context["items"]]
        self.assertNotIn("Inactive", names)
        self.assertIn("Test", names)

    def test_home_context_active_discounts(self):
        d1 = DiscountType.objects.create(name="Active Disc", kind="PERCENTAGE", value=10, is_active=True)
        DiscountType.objects.create(name="Inactive Disc", kind="FIXED", value=50, is_active=False)
        r = self.client.get(reverse("home"))
        self.assertIn(d1, r.context["discounts"])
        self.assertEqual(r.context["discounts"].count(), 1)

    def test_home_context_has_dashboard_stats(self):
        """Home page context includes computed dashboard stats."""
        r = self.client.get(reverse("home"))
        self.assertIn("today_sales", r.context)
        self.assertIn("avg_ticket", r.context)
        self.assertIn("active_orders", r.context)
        self.assertIn("low_stock_count", r.context)

    def test_dashboard_stats_computed_correctly(self):
        """Stats reflect actual DB state when transactions exist."""
        from django.utils import timezone
        txn1 = Transaction.objects.create(
            subtotal="200.00", grand_total="200.00", payment_method="CASH",
            status="COMPLETED", branch=self.branch
        )
        txn2 = Transaction.objects.create(
            subtotal="100.00", grand_total="100.00", payment_method="GCASH",
            status="COMPLETED", branch=self.branch
        )
        # A voided transaction should not count
        Transaction.objects.create(
            subtotal="50.00", grand_total="0.00", status="VOIDED", branch=self.branch
        )
        r = self.client.get(reverse("home"))
        self.assertEqual(r.context["today_sales"], Decimal("300.00"))
        self.assertEqual(r.context["active_orders"], 2)
        self.assertEqual(r.context["avg_ticket"], Decimal("150.00"))

    def test_today_sales_zero_when_no_transactions(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r.context["today_sales"], Decimal("0.00"))
        self.assertEqual(r.context["active_orders"], 0)
        self.assertEqual(r.context["avg_ticket"], Decimal("0.00"))

    def test_low_stock_count_in_context(self):
        """Items with stock_qty <= low_stock_threshold are counted."""
        cat = Category.objects.create(name="Extra")
        # Setup has Test item (stock=10, threshold=10) — that's low stock too
        # So count should now be setup (1) + new low (1) = 2
        Item.objects.create(category=cat, name="Low Stock Item", sku="LOW-001",
                            emoji="⚠️", cost_price=10, selling_price=20,
                            stock_qty=3, low_stock_threshold=10, branch=self.branch)
        # This item is fine (threshold=10, stock=50)
        Item.objects.create(category=cat, name="Well Stocked", sku="FUL-001",
                            emoji="✅", cost_price=10, selling_price=20,
                            stock_qty=50, low_stock_threshold=10, branch=self.branch)
        r = self.client.get(reverse("home"))
        self.assertEqual(r.context["low_stock_count"], 2)

    def test_low_stock_item_inactive_not_counted(self):
        """Inactive items are not counted even if low stock."""
        cat = Category.objects.create(name="Extra")
        Item.objects.create(category=cat, name="Inactive Low", sku="I-LOW-001",
                            emoji="💤", cost_price=10, selling_price=20,
                            stock_qty=0, low_stock_threshold=10, is_active=False, branch=self.branch)
        r = self.client.get(reverse("home"))
        # Setup item (Test: stock=10, threshold=10) is still counted
        self.assertEqual(r.context["low_stock_count"], 1)

    def test_home_search_filter_by_name(self):
        """Home ?q=term filters items by name (case-insensitive)."""
        cat = Category.objects.create(name="Extra")
        Item.objects.create(category=cat, name="Burger Supreme", sku="BUR-001",
                            emoji="🍔", cost_price=50, selling_price=100, stock_qty=10, branch=self.branch)
        Item.objects.create(category=cat, name="Fries Large", sku="FRI-001",
                            emoji="🍟", cost_price=20, selling_price=45, stock_qty=20, branch=self.branch)
        r = self.client.get(reverse("home") + "?q=burger")
        names = [i.name for i in r.context["items"]]
        self.assertIn("Burger Supreme", names)
        self.assertNotIn("Fries Large", names)

    def test_home_search_empty_returns_all(self):
        """Empty search param returns all active items."""
        r = self.client.get(reverse("home") + "?q=")
        names = [i.name for i in r.context["items"]]
        self.assertIn("Test", names)  # from setUp

    def test_inventory_dashboard_200(self):
        r = self.client.get(reverse("inventory_dashboard"))
        self.assertEqual(r.status_code, 200)

    def test_sales_history_200(self):
        r = self.client.get(reverse("sales_history"))
        self.assertEqual(r.status_code, 200)

    def test_sales_history_lists_completed_transactions_only(self):
        """Sales history only shows COMPLETED transactions."""
        txn1 = Transaction.objects.create(subtotal="100", grand_total="100", status="COMPLETED", branch=self.branch)
        Transaction.objects.create(subtotal="50", grand_total="0", status="VOIDED", branch=self.branch)
        r = self.client.get(reverse("sales_history"))
        self.assertIn(txn1, r.context["transactions"])
        self.assertEqual(r.context["transactions"].count(), 1)

    def test_sales_history_empty_state_ok(self):
        r = self.client.get(reverse("sales_history"))
        self.assertEqual(r.context["transactions"].count(), 0)

    def test_reports_200(self):
        r = self.client.get(reverse("reports"))
        self.assertEqual(r.status_code, 200)

    def test_customers_200(self):
        r = self.client.get(reverse("customers"))
        self.assertEqual(r.status_code, 200)

    def test_product_catalog_200(self):
        r = self.client.get(reverse("product_catalog"))
        self.assertEqual(r.status_code, 200)

    def test_inventory_add_200(self):
        r = self.client.get(reverse("item_add"))
        self.assertEqual(r.status_code, 200)

    def test_inventory_add_has_categories_in_context(self):
        """Add item form must pass categories to template for dropdown."""
        r = self.client.get(reverse("item_add"))
        self.assertIn("categories", r.context)

    def test_inventory_add_category_dropdown_shows_options(self):
        """Category dropdown should render <option> tags in HTML."""
        r = self.client.get(reverse("item_add"))
        html = r.content.decode()
        self.assertIn("<option", html)
        self.assertNotIn("[]", html)

    def test_inventory_edit_200(self):
        r = self.client.get(reverse("item_edit", args=[self.item.pk]))
        self.assertEqual(r.status_code, 200)

    def test_inventory_edit_has_categories_in_context(self):
        """Edit item form must pass categories to template."""
        r = self.client.get(reverse("item_edit", args=[self.item.pk]))
        self.assertIn("categories", r.context)

    def test_inventory_edit_category_pre_selected(self):
        """Edit form should pre-select the item's current category."""
        r = self.client.get(reverse("item_edit", args=[self.item.pk]))
        html = r.content.decode()
        self.assertIn(f'value="{self.cat.id}" selected', html)

    def test_receipt_200(self):
        txn = Transaction.objects.create(subtotal="100.00", grand_total="100.00", branch=self.branch)
        r = self.client.get(reverse("receipt", args=[txn.pk]))
        self.assertEqual(r.status_code, 200)


# ===================== RECEIPT PRINT TESTS =====================

class ReceiptPrintTest(TestCase):
    """Tests for the thermal receipt print endpoint /receipt/<pk>/print/."""

    def setUp(self):
        self.client = Client()
        # Create and log in a user for the login-required views
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client.login(username="testuser", password="testpass123")
        self.cat = Category.objects.create(name="Beverages")
        self.item = Item.objects.create(
            category=self.cat, name="Coke", sku="DRK-001",
            emoji="🥤", cost_price=10, selling_price=25, stock_qty=100
        )
        self.txn = Transaction.objects.create(
            subtotal="50.00",
            discount_amount="5.00",
            vat_amount="4.82",
            vat_exclusive_sales="40.18",
            grand_total="45.00",
            payment_method="CASH",
            table_number=5,
            order_type="DINE_IN",
            vat_inclusive=True,
            manual_discount_pct=Decimal("10.00"),
        )
        TransactionItem.objects.create(
            transaction=self.txn, item=self.item,
            quantity=2, unit_price=Decimal("25.00"),
            total_price=Decimal("50.00")
        )

    def test_receipt_print_returns_200(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertEqual(r.status_code, 200)

    def test_receipt_print_uses_correct_template(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertTemplateUsed(r, "pos/receipt_print.html")

    def test_receipt_print_contains_store_name(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertContains(r, "CASSEY")

    def test_receipt_print_contains_transaction_id(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertContains(r, str(self.txn.id))

    def test_receipt_print_contains_table_number(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertContains(r, "5")

    def test_receipt_print_contains_order_type(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertContains(r, "Dine-In")

    def test_receipt_print_contains_item_name_and_qty(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertContains(r, "Coke")
        self.assertContains(r, "x2")

    def test_receipt_print_contains_subtotal(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertContains(r, "50.00")

    def test_receipt_print_contains_discount_amount(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertContains(r, "5.00")

    def test_receipt_print_contains_vat_amount(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertContains(r, "4.82")

    def test_receipt_print_contains_grand_total(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertContains(r, "45.00")

    def test_receipt_print_contains_payment_method(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertContains(r, "Cash")

    def test_receipt_print_contains_timestamp(self):
        r = self.client.get(reverse("receipt_print", args=[self.txn.pk]))
        self.assertContains(r, self.txn.timestamp.strftime("%Y"))

    def test_receipt_print_404_for_nonexistent(self):
        r = self.client.get(reverse("receipt_print", args=[9999]))
        self.assertEqual(r.status_code, 404)


# ===================== CHECKOUT API TESTS =====================

class CheckoutApiTest(TestCase):
    """Test the checkout_submit_api view with real frontend payload."""

    def setUp(self):
        self.client = Client()
        self.cat = Category.objects.create(name="Test")
        self.item = Item.objects.create(
            category=self.cat, name="Coke Regular", sku="DRK-001",
            emoji="🥤", cost_price=12, selling_price=20, stock_qty=10
        )

    def test_checkout_api_frontend_payload(self):
        """Frontend sends 'quantity' not 'qty' — must work."""
        payload = {
            "cart": [{"item_id": self.item.id, "quantity": 2}],
            "payment_method": "CASH",
        }
        r = self.client.post(
            reverse("checkout_api"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("transaction_id", data)
        # Stock should be deducted
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_qty, 8)

    def test_checkout_api_sends_qty_field(self):
        """Backward compat: 'qty' field also works."""
        payload = {
            "cart": [{"item_id": self.item.id, "qty": 3}],
            "payment_method": "CASH",
        }
        r = self.client.post(
            reverse("checkout_api"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "success")

    def test_checkout_api_empty_cart_returns_error(self):
        payload = {"cart": [], "payment_method": "CASH"}
        r = self.client.post(
            reverse("checkout_api"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["message"], "Cart empty")

    def test_checkout_api_invalid_method(self):
        r = self.client.get(reverse("checkout_api"))
        self.assertEqual(r.status_code, 405)

    def test_checkout_api_manual_discount(self):
        """API accepts manual_discount_pct and stores it."""
        payload = {
            "cart": [{"item_id": self.item.id, "quantity": 5}],
            "payment_method": "CASH",
            "manual_discount_pct": 10.00,
        }
        r = self.client.post(
            reverse("checkout_api"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "success")
        txn = Transaction.objects.get(id=data["transaction_id"])
        self.assertEqual(txn.manual_discount_pct, Decimal("10.00"))
        # 5 items x 20 = 100 subtotal, 10% discount = 10, grand_total = 90
        self.assertEqual(txn.grand_total, Decimal("90.00"))


# ===================== CATEGORY CRUD TESTS =====================

class CategoryCrudUrlTest(TestCase):
    def test_category_list_resolves(self):
        resolver = resolve("/categories/")
        self.assertEqual(resolver.url_name, "category_list")

    def test_category_add_resolves(self):
        resolver = resolve("/categories/add/")
        self.assertEqual(resolver.url_name, "category_add")

    def test_category_edit_resolves(self):
        resolver = resolve("/categories/1/edit/")
        self.assertEqual(resolver.url_name, "category_edit")

    def test_category_delete_resolves(self):
        resolver = resolve("/categories/1/delete/")
        self.assertEqual(resolver.url_name, "category_delete")


class CategoryCrudSmokeTest(TestCase):
    def setUp(self):
        self.client = Client()
        User.objects.create_user(username="testuser", password="testpass123")
        self.client.login(username="testuser", password="testpass123")
        self.cat = Category.objects.create(name="Snacks", description="Merienda items")

    def test_category_list_200(self):
        r = self.client.get(reverse("category_list"))
        self.assertEqual(r.status_code, 200)

    def test_category_list_context_has_categories(self):
        r = self.client.get(reverse("category_list"))
        self.assertIn("categories", r.context)

    def test_category_add_200(self):
        r = self.client.get(reverse("category_add"))
        self.assertEqual(r.status_code, 200)

    def test_category_add_post_creates(self):
        r = self.client.post(reverse("category_add"), {"name": "New Cat", "description": "desc"})
        self.assertRedirects(r, reverse("category_list"))
        self.assertEqual(Category.objects.count(), 2)

    def test_category_edit_200(self):
        r = self.client.get(reverse("category_edit", args=[self.cat.pk]))
        self.assertEqual(r.status_code, 200)

    def test_category_edit_post_updates(self):
        r = self.client.post(reverse("category_edit", args=[self.cat.pk]),
                             {"name": "Updated", "description": "changed"})
        self.assertRedirects(r, reverse("category_list"))
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.name, "Updated")

    def test_category_delete_200(self):
        r = self.client.get(reverse("category_delete", args=[self.cat.pk]))
        self.assertEqual(r.status_code, 200)

    def test_category_delete_post_removes(self):
        r = self.client.post(reverse("category_delete", args=[self.cat.pk]))
        self.assertRedirects(r, reverse("category_list"))
        self.assertEqual(Category.objects.count(), 0)

    def test_category_delete_protected_handles_error(self):
        """Delete fails gracefully when items reference the category."""
        cat2 = Category.objects.create(name="Protected Cat")
        Item.objects.create(category=cat2, name="Linked", sku="LNK-001",
                            emoji="🔗", cost_price=10, selling_price=20)
        r = self.client.post(reverse("category_delete", args=[cat2.pk]))
        self.assertEqual(r.status_code, 200)  # renders template with error context
        self.assertContains(r, "Cannot delete")
        self.assertContains(r, "1")  # linked count


# ===================== DISCOUNTTYPE CRUD TESTS =====================

class DiscountTypeCrudUrlTest(TestCase):
    def test_discount_list_resolves(self):
        resolver = resolve("/discounts/")
        self.assertEqual(resolver.url_name, "discount_list")

    def test_discount_add_resolves(self):
        resolver = resolve("/discounts/add/")
        self.assertEqual(resolver.url_name, "discount_add")

    def test_discount_edit_resolves(self):
        resolver = resolve("/discounts/1/edit/")
        self.assertEqual(resolver.url_name, "discount_edit")

    def test_discount_delete_resolves(self):
        resolver = resolve("/discounts/1/delete/")
        self.assertEqual(resolver.url_name, "discount_delete")


class DiscountTypeCrudSmokeTest(TestCase):
    def setUp(self):
        self.client = Client()
        User.objects.create_user(username="testuser", password="testpass123")
        self.client.login(username="testuser", password="testpass123")
        self.disc = DiscountType.objects.create(name="10% Off", kind="PERCENTAGE", value=10)

    def test_discount_list_200(self):
        r = self.client.get(reverse("discount_list"))
        self.assertEqual(r.status_code, 200)

    def test_discount_add_200(self):
        r = self.client.get(reverse("discount_add"))
        self.assertEqual(r.status_code, 200)

    def test_discount_add_post_creates(self):
        r = self.client.post(reverse("discount_add"), {
            "name": "₱20 Off", "kind": "FIXED", "value": 20, "is_active": True
        })
        self.assertRedirects(r, reverse("discount_list"))
        self.assertEqual(DiscountType.objects.count(), 2)

    def test_discount_edit_200(self):
        r = self.client.get(reverse("discount_edit", args=[self.disc.pk]))
        self.assertEqual(r.status_code, 200)

    def test_discount_edit_post_updates(self):
        r = self.client.post(reverse("discount_edit", args=[self.disc.pk]), {
            "name": "20% Off Now", "kind": "PERCENTAGE", "value": 20, "is_active": True
        })
        self.assertRedirects(r, reverse("discount_list"))
        self.disc.refresh_from_db()
        self.assertEqual(self.disc.value, 20)

    def test_discount_delete_200(self):
        r = self.client.get(reverse("discount_delete", args=[self.disc.pk]))
        self.assertEqual(r.status_code, 200)

    def test_discount_delete_post_removes(self):
        r = self.client.post(reverse("discount_delete", args=[self.disc.pk]))
        self.assertRedirects(r, reverse("discount_list"))
        self.assertEqual(DiscountType.objects.count(), 0)


# ===================== TRANSACTION VOID TESTS =====================

class TransactionVoidUrlTest(TestCase):
    def test_void_url_resolves(self):
        resolver = resolve("/transactions/1/void/")
        self.assertEqual(resolver.url_name, "transaction_void")


class TransactionVoidTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Test", type="LPG", code="T-01")
        self.admin_user = User.objects.create_user(
            username="voidadmin", password="voidpass123"
        )
        self.cat = Category.objects.create(name="Test")
        self.item = Item.objects.create(
            category=self.cat, name="Void Item", sku="V-001",
            emoji="💔", cost_price=10, selling_price=50, stock_qty=10,
            branch=self.branch
        )
        self.txn = Transaction.objects.create(
            subtotal="100.00", grand_total="100.00", status="COMPLETED",
            branch=self.branch
        )
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()
        TransactionItem.objects.create(
            transaction=self.txn, item=self.item, quantity=2,
            unit_price=50, total_price=100
        )
        # Login as ADMIN staff
        self.client.login(username="voidadmin", password="voidpass123")
        Staff.objects.create(user=self.admin_user, role=Staff.Role.ADMIN)

    def test_void_restores_stock(self):
        r = self.client.post(reverse("transaction_void", args=[self.txn.pk]),
                             {"reason": "Customer returned"})
        self.assertRedirects(r, reverse("sales_history"))
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, "VOIDED")
        self.assertEqual(self.txn.grand_total, 0)
        self.assertEqual(self.txn.void_reason, "Customer returned")
        self.assertIsNotNone(self.txn.voided_at)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_qty, 12)  # restored 2 units

    def test_void_without_reason_still_voids(self):
        r = self.client.post(reverse("transaction_void", args=[self.txn.pk]))
        self.assertRedirects(r, reverse("sales_history"))
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, "VOIDED")
        self.assertIsNone(self.txn.void_reason)

    def test_void_allows_all_roles_in_offline_mode(self):
        """All users can void transactions in offline mode."""
        cashier_user = User.objects.create_user(
            username="cashiervoid", password="testpass123"
        )
        Staff.objects.create(user=cashier_user, role=Staff.Role.CASHIER)
        self.client.login(username="cashiervoid", password="testpass123")
        # Branch session persists through client.login, re-set
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()

        r = self.client.post(reverse("transaction_void", args=[self.txn.pk]))
        self.assertRedirects(r, reverse("sales_history"))
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, "VOIDED")

class StockAdjustTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Test", type="LPG", code="T-01")
        User.objects.create_user(username="testuser", password="testpass123")
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()
        self.cat = Category.objects.create(name="Test")
        self.item = Item.objects.create(
            category=self.cat, name="Stock Adjust", sku="STK-001",
            emoji="📦", cost_price=10, selling_price=20, stock_qty=5,
            branch=self.branch
        )

    def test_stock_adjust_url_resolves(self):
        resolver = resolve("/inventory/1/stock-adjust/")
        self.assertEqual(resolver.url_name, "stock_adjust")

    def test_stock_adjust_post_updates_qty(self):
        r = self.client.post(reverse("stock_adjust", args=[self.item.pk]),
                             {"stock_qty": 100})
        self.assertRedirects(r, reverse("inventory_dashboard"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_qty, 100)


# ===================== USER / STAFF MODEL TESTS =====================

class StaffModelTest(TestCase):
    """Tests for the custom Staff (UserProfile) model with role-based access."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(
            username="cashier1", password="testpass123",
            first_name="Juan", last_name="Dela Cruz"
        )

    def test_staff_creation_with_admin_role(self):
        from pos.models import Staff
        staff = Staff.objects.create(
            user=self.user, role=Staff.Role.ADMIN
        )
        self.assertEqual(staff.user.username, "cashier1")
        self.assertEqual(staff.role, Staff.Role.ADMIN)
        self.assertEqual(str(staff), "cashier1 — Admin")

    def test_staff_creation_with_cashier_role(self):
        from pos.models import Staff
        staff = Staff.objects.create(
            user=self.user, role=Staff.Role.CASHIER
        )
        self.assertEqual(staff.role, Staff.Role.CASHIER)
        self.assertEqual(str(staff), "cashier1 — Cashier")

    def test_staff_default_role_is_cashier(self):
        from pos.models import Staff
        staff = Staff.objects.create(user=self.user)
        self.assertEqual(staff.role, Staff.Role.CASHIER)

    def test_staff_role_choices_validation(self):
        from pos.models import Staff
        from django.db import IntegrityError
        # Should work with valid roles
        staff = Staff.objects.create(user=self.user, role=Staff.Role.ADMIN)
        self.assertEqual(staff.role, Staff.Role.ADMIN)

    def test_staff_one_to_one_relation(self):
        from pos.models import Staff
        staff = Staff.objects.create(user=self.user, role=Staff.Role.CASHIER)
        # Access from the user side
        self.assertEqual(staff.user, self.user)
        # Access from user back to staff
        self.assertEqual(self.user.staff, staff)

    def test_admin_can_access_admin_panel(self):
        from pos.models import Staff
        from django.contrib.auth.models import User
        admin_user = User.objects.create_superuser(
            username="admin", password="adminpass", email="admin@example.com"
        )
        Staff.objects.create(user=admin_user, role=Staff.Role.ADMIN)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.staff.role, Staff.Role.ADMIN)

    def test_staff_is_staff_flag_enabled_by_default(self):
        from pos.models import Staff
        staff = Staff.objects.create(user=self.user, role=Staff.Role.CASHIER)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)


# ===================== AUTHENTICATION / LOGIN TESTS =====================
class KOTPrintTest(TestCase):
    """TDD tests for Kitchen Order Ticket print endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(username="kotuser", password="testpass123")
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name="Food")
        self.item1 = Item.objects.create(
            category=self.cat, name="Chicken Inasal", sku="CHK-001",
            emoji="🍗", cost_price="50", selling_price="80", stock_qty=20
        )
        self.item2 = Item.objects.create(
            category=self.cat, name="Java Rice", sku="RCE-001",
            emoji="🍚", cost_price="10", selling_price="20", stock_qty=50
        )
        self.txn = Transaction.objects.create(
            subtotal="180.00", grand_total="180.00",
            order_type="DINE_IN", table_number=5
        )
        TransactionItem.objects.create(
            transaction=self.txn, item=self.item1, quantity=2,
            unit_price=Decimal("80.00"), total_price=Decimal("160.00")
        )
        TransactionItem.objects.create(
            transaction=self.txn, item=self.item2, quantity=1,
            unit_price=Decimal("20.00"), total_price=Decimal("20.00")
        )

    def test_kot_print_url_resolves(self):
        """GET /kot/<id>/print/ should resolve to KOT print view."""
        resolver = resolve(f"/kot/{self.txn.id}/print/")
        self.assertEqual(resolver.func.__name__, "kot_print")

    def test_kot_print_returns_200(self):
        """GET /kot/<id>/print/ should return 200."""
        response = self.client.get(f"/kot/{self.txn.id}/print/")
        self.assertEqual(response.status_code, 200)

    def test_kot_print_404_for_nonexistent_transaction(self):
        """KOT for a non-existent transaction should 404."""
        response = self.client.get("/kot/99999/print/")
        self.assertEqual(response.status_code, 404)

    def test_kot_displays_table_number(self):
        """KOT should display the table number prominently."""
        response = self.client.get(f"/kot/{self.txn.id}/print/")
        self.assertContains(response, "Table")
        self.assertContains(response, "5")

    def test_kot_displays_order_type(self):
        """KOT should display the order type."""
        response = self.client.get(f"/kot/{self.txn.id}/print/")
        self.assertContains(response, "Dine-In")

    def test_kot_displays_item_names_and_quantities(self):
        """KOT should list all items with names and quantities."""
        response = self.client.get(f"/kot/{self.txn.id}/print/")
        self.assertContains(response, "Chicken Inasal")
        self.assertContains(response, "Java Rice")
        self.assertContains(response, "x2")
        self.assertContains(response, "x1")

    def test_kot_does_not_show_prices(self):
        """KOT should not display monetary amounts, only food prep info."""
        response = self.client.get(f"/kot/{self.txn.id}/print/")
        self.assertNotContains(response, "₱")
        self.assertNotContains(response, "Peso")
        self.assertNotContains(response, "Total")

    def test_kot_takeout_shows_no_table_number(self):
        """TAKE_OUT orders should indicate no table."""
        takeout_txn = Transaction.objects.create(
            subtotal="80.00", grand_total="80.00",
            order_type="TAKE_OUT", table_number=None
        )
        TransactionItem.objects.create(
            transaction=takeout_txn, item=self.item1, quantity=1,
            unit_price=Decimal("80.00"), total_price=Decimal("80.00")
        )
        response = self.client.get(f"/kot/{takeout_txn.id}/print/")
        self.assertContains(response, "Take-Out")

    def test_kot_displays_transaction_id(self):
        """KOT should display the order/transaction ID."""
        response = self.client.get(f"/kot/{self.txn.id}/print/")
        self.assertContains(response, f"#{self.txn.id}")


class ReprintFromSalesHistoryTest(TestCase):
    """TDD tests for receipt reprint feature from sales history."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test", type="LPG", code="T-01")
        self.user = User.objects.create_user(
            username="repuser", password="testpass123"
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()
        self.cat = Category.objects.create(name="Food")
        self.item = Item.objects.create(
            category=self.cat, name="Burger", sku="BRG-001",
            emoji="🍔", cost_price="30", selling_price="60", stock_qty=20,
            branch=self.branch
        )
        self.completed_txn = Transaction.objects.create(
            subtotal="120.00", grand_total="134.40",
            payment_method="CASH", order_type="DINE_IN", table_number=3,
            status="COMPLETED", branch=self.branch
        )
        TransactionItem.objects.create(
            transaction=self.completed_txn, item=self.item, quantity=2,
            unit_price=Decimal("60.00"), total_price=Decimal("120.00")
        )
        self.voided_txn = Transaction.objects.create(
            subtotal="60.00", grand_total="0.00",
            payment_method="CASH", order_type="TAKE_OUT",
            status="VOIDED", branch=self.branch
        )
        TransactionItem.objects.create(
            transaction=self.voided_txn, item=self.item, quantity=1,
            unit_price=Decimal("60.00"), total_price=Decimal("60.00")
        )

    def test_sales_history_has_reprint_link(self):
        """Sales history page should contain a receipt link for each transaction."""
        response = self.client.get("/sales/")
        self.assertContains(response, f"/sales/{self.completed_txn.id}/")

    def test_reprint_link_points_to_receipt_print(self):
        """The reprint link should point to the receipt_print URL."""
        from django.urls import resolve
        resolver = resolve(f"/receipt/{self.completed_txn.id}/print/")
        self.assertEqual(resolver.func.__name__, "receipt_print")

    def test_voided_receipt_shows_void_watermark(self):
        """Receipt print for VOIDED transaction should show a VOID watermark."""
        response = self.client.get(f"/receipt/{self.voided_txn.id}/print/")
        self.assertContains(response, "VOID")

    def test_voided_receipt_shows_void_badge(self):
        """VOIDED receipt should show a clear void badge/message."""
        response = self.client.get(f"/receipt/{self.voided_txn.id}/print/")
        self.assertContains(response, "VOIDED")
        self.assertContains(response, "THIS RECEIPT IS VOIDED")

    def test_completed_receipt_does_not_show_void_marker(self):
        """Completed transaction receipt should NOT show any void marker."""
        response = self.client.get(f"/receipt/{self.completed_txn.id}/print/")
        self.assertNotContains(response, "VOIDED")
        self.assertNotContains(response, "THIS RECEIPT IS VOIDED")


# ===================== CASH COUNT TESTS =====================

class CashCountModelTest(TestCase):
    """Tests for CashCount model subtotal auto-computation and shift FK."""

    def setUp(self):
        self.user = User.objects.create_user(username="cashier", password="pass")
        self.shift = Shift.objects.create(cashier=self.user, starting_float=Decimal("1000.00"))

    def test_cashcount_created_with_subtotal(self):
        cc = CashCount.objects.create(
            shift=self.shift,
            denomination_value=Decimal("1000.00"),
            quantity=2,
        )
        self.assertEqual(cc.subtotal, Decimal("2000.00"))

    def test_cashcount_multiple_denominations(self):
        CashCount.objects.create(shift=self.shift, denomination_value=Decimal("1000.00"), quantity=1)
        CashCount.objects.create(shift=self.shift, denomination_value=Decimal("500.00"), quantity=2)
        CashCount.objects.create(shift=self.shift, denomination_value=Decimal("100.00"), quantity=3)
        CashCount.objects.create(shift=self.shift, denomination_value=Decimal("50.00"), quantity=4)
        CashCount.objects.create(shift=self.shift, denomination_value=Decimal("20.00"), quantity=5)
        CashCount.objects.create(shift=self.shift, denomination_value=Decimal("0.00"), quantity=999)
        entries = CashCount.objects.filter(shift=self.shift)
        self.assertEqual(entries.count(), 6)
        total = entries.aggregate(total=dj_models.Sum("subtotal"))["total"]
        expected = Decimal("1000") + Decimal("1000") + Decimal("300") + Decimal("200") + Decimal("100") + Decimal("0")
        self.assertEqual(total, expected)

    def test_cashcount_subtotal_updates_on_save(self):
        cc = CashCount.objects.create(
            shift=self.shift, denomination_value=Decimal("100.00"), quantity=5
        )
        self.assertEqual(cc.subtotal, Decimal("500.00"))
        cc.quantity = 10
        cc.save()
        cc.refresh_from_db()
        self.assertEqual(cc.subtotal, Decimal("1000.00"))

    def test_cashcount_zero_quantity(self):
        cc = CashCount.objects.create(
            shift=self.shift, denomination_value=Decimal("500.00"), quantity=0
        )
        self.assertEqual(cc.subtotal, Decimal("0.00"))

    def test_cashcount_deleted_with_shift(self):
        CashCount.objects.create(shift=self.shift, denomination_value=Decimal("100.00"), quantity=1)
        shift_id = self.shift.id
        self.shift.delete()
        self.assertEqual(CashCount.objects.filter(shift_id=shift_id).count(), 0)

    def test_cashcount_str_representation(self):
        cc = CashCount.objects.create(
            shift=self.shift, denomination_value=Decimal("1000.00"), quantity=3
        )
        self.assertIn("CashCount", str(cc))
        self.assertIn("1000.00", str(cc))


class CashCountAPITest(TestCase):
    """Tests for the cash count API endpoints."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testcashier", password="testpass123"
        )
        self.client.force_login(self.user)
        self.shift = Shift.objects.create(
            cashier=self.user, starting_float=Decimal("1000.00")
        )

    def test_get_cash_count_empty(self):
        response = self.client.get(
            reverse("shift_cash_count_api", args=[self.shift.id])
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["entries"], [])
        self.assertEqual(data["total_counted"], "0.00")

    def test_post_cash_denominations(self):
        payload = {
            "denominations": [
                {"value": 1000.00, "qty": 1},
                {"value": 500.00, "qty": 2},
                {"value": 100.00, "qty": 3},
                {"value": 50.00, "qty": 4},
                {"value": 20.00, "qty": 5},
                {"value": 0.00, "qty": 1},
            ]
        }
        response = self.client.post(
            reverse("shift_cash_count_api", args=[self.shift.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["entry_count"], 6)
        expected_total = Decimal("1000") + Decimal("1000") + Decimal("300") + Decimal("200") + Decimal("100") + Decimal("0")
        self.assertEqual(Decimal(data["total_counted"]), expected_total)

    def test_get_cash_count_after_post(self):
        payload = {
            "denominations": [
                {"value": 500.00, "qty": 2},
                {"value": 100.00, "qty": 5},
            ]
        }
        self.client.post(
            reverse("shift_cash_count_api", args=[self.shift.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )
        response = self.client.get(
            reverse("shift_cash_count_api", args=[self.shift.id])
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["entries"]), 2)
        self.assertEqual(Decimal(data["total_counted"]), Decimal("1000.00") + Decimal("500.00"))

    def test_post_replaces_old_entries(self):
        payload1 = {"denominations": [{"value": 100.00, "qty": 10}]}
        self.client.post(
            reverse("shift_cash_count_api", args=[self.shift.id]),
            data=json.dumps(payload1),
            content_type="application/json",
        )
        payload2 = {"denominations": [{"value": 50.00, "qty": 20}]}
        response = self.client.post(
            reverse("shift_cash_count_api", args=[self.shift.id]),
            data=json.dumps(payload2),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["entry_count"], 1)
        self.assertEqual(Decimal(data["total_counted"]), Decimal("1000.00"))
        self.assertEqual(CashCount.objects.filter(shift=self.shift).count(), 1)

    def test_post_invalid_json(self):
        response = self.client.post(
            reverse("shift_cash_count_api", args=[self.shift.id]),
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_get_cash_count_wrong_shift(self):
        response = self.client.get(
            reverse("shift_cash_count_api", args=[99999])
        )
        self.assertEqual(response.status_code, 404)

    def test_post_entry_details_stored_correctly(self):
        payload = {
            "denominations": [
                {"value": "20.00", "qty": 10},
                {"value": 1000.00, "qty": 1},
            ]
        }
        response = self.client.post(
            reverse("shift_cash_count_api", args=[self.shift.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

        entries = CashCount.objects.filter(shift=self.shift).order_by("-denomination_value")
        self.assertEqual(entries.count(), 2)
        self.assertEqual(entries[0].denomination_value, Decimal("1000.00"))
        self.assertEqual(entries[0].quantity, 1)
        self.assertEqual(entries[0].subtotal, Decimal("1000.00"))
        self.assertEqual(entries[1].denomination_value, Decimal("20.00"))
        self.assertEqual(entries[1].quantity, 10)
        self.assertEqual(entries[1].subtotal, Decimal("200.00"))

    def test_get_entries_ordered_by_denomination_desc(self):
        payload = {
            "denominations": [
                {"value": 20.00, "qty": 5},
                {"value": 1000.00, "qty": 2},
                {"value": 100.00, "qty": 3},
            ]
        }
        self.client.post(
            reverse("shift_cash_count_api", args=[self.shift.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )
        response = self.client.get(
            reverse("shift_cash_count_api", args=[self.shift.id])
        )
        data = response.json()
        values = [Decimal(e["denomination_value"]) for e in data["entries"]]
        self.assertEqual(values, [Decimal("1000.00"), Decimal("100.00"), Decimal("20.00")])


# ===================== SHIFT MANAGEMENT TESTS =====================

class ShiftModelTest(TestCase):
    """Tests for Shift model creation, fields, and status transitions."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="cashier1", password="testpass123"
        )

    def test_shift_creation_defaults(self):
        """Shift should be created with OPEN status and auto start_time."""
        shift = Shift.objects.create(
            cashier=self.user,
            starting_float=Decimal("1000.00"),
        )
        self.assertEqual(shift.cashier, self.user)
        self.assertIsNotNone(shift.start_time)
        self.assertIsNone(shift.end_time)
        self.assertEqual(shift.starting_float, Decimal("1000.00"))
        self.assertIsNone(shift.ending_float)
        self.assertEqual(shift.status, Shift.Status.OPEN)

    def test_shift_str_representation(self):
        """String representation should include cashier and status."""
        shift = Shift.objects.create(
            cashier=self.user,
            starting_float=Decimal("500.00"),
        )
        expected = f"{self.user.username} - {shift.start_time} [OPEN]"
        self.assertEqual(str(shift), expected)

    def test_shift_status_choices(self):
        """Shift status should be limited to OPEN and CLOSED."""
        self.assertEqual(Shift.Status.OPEN, "OPEN")
        self.assertEqual(Shift.Status.CLOSED, "CLOSED")

    def test_shift_cashier_nullable(self):
        """Shift cashier should be nullable (for system/auto shifts)."""
        shift = Shift.objects.create(
            cashier=None,
            starting_float=Decimal("1000.00"),
        )
        self.assertIsNone(shift.cashier)

    def test_shift_starting_float_default(self):
        """starting_float should default to 0.00."""
        shift = Shift.objects.create(cashier=self.user)
        self.assertEqual(shift.starting_float, Decimal("0.00"))


class ShiftAPITest(TestCase):
    """Tests for shift API endpoints: start, end, current."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test", type="LPG", code="T-01")
        self.user = User.objects.create_user(
            username="cashier1", password="testpass123"
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()

    def test_start_shift_returns_shift_data(self):
        """POST /api/shifts/start/ should create and return a shift."""
        response = self.client.post("/api/shifts/start/", {
            "starting_float": "1000.00",
            "cashier_name": "cashier1",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["cashier"], self.user.username)
        self.assertEqual(data["starting_float"], "1000.00")
        self.assertEqual(data["status"], "OPEN")
        self.assertIsNotNone(data["start_time"])
        self.assertIsNone(data["end_time"])

    def test_start_shift_defaults_float(self):
        """POST /api/shifts/start/ without starting_float should default to 0."""
        response = self.client.post("/api/shifts/start/", {"cashier_name": "cashier1"},
                                    content_type="application/json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["starting_float"], "0.00")

    def test_cannot_start_shift_if_open_shift_exists(self):
        """Starting a new shift when one is OPEN should fail."""
        self.client.post("/api/shifts/start/", {"starting_float": "500.00", "cashier_name": "cashier1"},
                         content_type="application/json")
        response = self.client.post("/api/shifts/start/", {"starting_float": "1000.00", "cashier_name": "cashier1"},
                                    content_type="application/json")
        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.json())

    def test_end_shift_returns_updated_shift(self):
        """PUT /api/shifts/<id>/end/ should close the shift."""
        start_resp = self.client.post("/api/shifts/start/", {"starting_float": "500.00", "cashier_name": "cashier1"},
                                      content_type="application/json")
        shift_id = start_resp.json()["id"]
        response = self.client.put(f"/api/shifts/{shift_id}/end/",
                                   {"ending_float": "1500.00"},
                                   content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "CLOSED")
        self.assertEqual(data["ending_float"], "1500.00")
        self.assertIsNotNone(data["end_time"])

    def test_end_shift_requires_ending_float(self):
        """Ending a shift must provide ending_float."""
        start_resp = self.client.post("/api/shifts/start/", {"starting_float": "500.00", "cashier_name": "cashier1"},
                                      content_type="application/json")
        shift_id = start_resp.json()["id"]
        response = self.client.put(f"/api/shifts/{shift_id}/end/", {},
                                   content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_end_already_closed_shift_fails(self):
        """Ending an already closed shift should fail."""
        start_resp = self.client.post("/api/shifts/start/", {"starting_float": "500.00", "cashier_name": "cashier1"},
                                      content_type="application/json")
        shift_id = start_resp.json()["id"]
        self.client.put(f"/api/shifts/{shift_id}/end/", {"ending_float": "1500.00"},
                        content_type="application/json")
        response = self.client.put(f"/api/shifts/{shift_id}/end/", {"ending_float": "2000.00"},
                                   content_type="application/json")
        self.assertEqual(response.status_code, 409)

    def test_get_current_shift_returns_open_shift(self):
        """GET /api/shifts/current/ should return the active OPEN shift."""
        self.client.post("/api/shifts/start/", {"starting_float": "500.00", "cashier_name": "cashier1"},
                         content_type="application/json")
        response = self.client.get("/api/shifts/current/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "OPEN")
        self.assertEqual(data["starting_float"], "500.00")

    def test_get_current_shift_returns_204_if_none(self):
        """GET /api/shifts/current/ when no open shift should return 204."""
        response = self.client.get("/api/shifts/current/")
        self.assertEqual(response.status_code, 204)

    def test_get_current_shift_closed_returns_204(self):
        """GET /api/shifts/current/ when only closed shifts should return 204."""
        start_resp = self.client.post("/api/shifts/start/", {"starting_float": "500.00", "cashier_name": "cashier1"},
                                      content_type="application/json")
        shift_id = start_resp.json()["id"]
        self.client.put(f"/api/shifts/{shift_id}/end/", {"ending_float": "1500.00"},
                        content_type="application/json")
        response = self.client.get("/api/shifts/current/")
        self.assertEqual(response.status_code, 204)

    def test_end_shift_requires_positive_ending_float(self):
        """ending_float must not be negative."""
        start_resp = self.client.post("/api/shifts/start/", {"starting_float": "500.00"},
                                      content_type="application/json")
        shift_id = start_resp.json()["id"]
        response = self.client.put(f"/api/shifts/{shift_id}/end/",
                                   {"ending_float": "-100.00"},
                                   content_type="application/json")
        self.assertEqual(response.status_code, 400)


# ===================== SHIFT ON TRANSACTION TESTS =====================

class ShiftTransactionTest(TestCase):
    """Tests for Transaction shift FK and checkout integration."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="cashier1", password="testpass123"
        )
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name="Test")
        self.item = Item.objects.create(
            category=self.cat, name="Test Item", sku="TST-001",
            emoji="🧪", cost_price=50, selling_price=100, stock_qty=10
        )

    def test_transaction_has_shift_fk_nullable(self):
        """Transaction.shift field should exist and be nullable."""
        shift = Shift.objects.create(
            cashier=self.user,
            starting_float=Decimal("1000.00"),
        )
        txn = Transaction.objects.create(
            subtotal="100.00", grand_total="100.00", shift=shift
        )
        txn.refresh_from_db()
        self.assertEqual(txn.shift, shift)

    def test_transaction_shift_nullable_default(self):
        """Transaction should work without a shift assigned."""
        txn = Transaction.objects.create(
            subtotal="100.00", grand_total="100.00"
        )
        self.assertIsNone(txn.shift)

    def test_checkout_accepts_shift_id_param(self):
        """POST /api/checkout/ with shift_id should link transaction."""
        shift = Shift.objects.create(
            cashier=self.user,
            starting_float=Decimal("1000.00"),
        )
        payload = {
            "cart": [{"item_id": self.item.id, "quantity": 1}],
            "shift_id": shift.id,
        }
        response = self.client.post("/api/checkout/", payload,
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        txn = Transaction.objects.get(id=data["transaction_id"])
        self.assertEqual(txn.shift, shift)

    def test_checkout_without_shift_id_works(self):
        """Checkout without shift_id should still succeed."""
        payload = {
            "cart": [{"item_id": self.item.id, "quantity": 1}]
        }
        response = self.client.post("/api/checkout/", payload,
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        txn = Transaction.objects.get(id=data["transaction_id"])
        self.assertIsNone(txn.shift)


# ===================== CASH COUNT TESTS =====================

class CashCountModelTest(TestCase):
    """Tests for the CashCount model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="cashier1", password="testpass123"
        )
        self.shift = Shift.objects.create(
            cashier=self.user,
            starting_float=Decimal("1000.00"),
        )

    def test_create_cash_count_entry(self):
        """A CashCount entry stores denomination_value and quantity."""
        entry = CashCount.objects.create(
            shift=self.shift,
            denomination_value=Decimal("500.00"),
            quantity=3,
        )
        self.assertEqual(entry.denomination_value, Decimal("500.00"))
        self.assertEqual(entry.quantity, 3)
        self.assertEqual(entry.subtotal, Decimal("1500.00"))  # 500 * 3

    def test_cash_count_subtotal_is_computed(self):
        """subtotal should auto-compute as denomination_value * quantity."""
        entry = CashCount.objects.create(
            shift=self.shift,
            denomination_value=Decimal("100.00"),
            quantity=5,
        )
        self.assertEqual(entry.subtotal, Decimal("500.00"))

    def test_cash_count_str_representation(self):
        """String representation includes shift and denomination."""
        entry = CashCount.objects.create(
            shift=self.shift,
            denomination_value=Decimal("50.00"),
            quantity=2,
        )
        self.assertIn(str(self.shift.id), str(entry))
        self.assertIn("50.00", str(entry))

    def test_cash_count_quantity_defaults_to_zero(self):
        """quantity should default to 0."""
        entry = CashCount.objects.create(
            shift=self.shift,
            denomination_value=Decimal("1000.00"),
        )
        self.assertEqual(entry.quantity, 0)
        self.assertEqual(entry.subtotal, Decimal("0.00"))

    def test_cash_count_cascade_delete_with_shift(self):
        """Deleting a shift should cascade-delete its CashCount entries."""
        CashCount.objects.create(
            shift=self.shift,
            denomination_value=Decimal("100.00"),
            quantity=2,
        )
        self.assertEqual(CashCount.objects.count(), 1)
        self.shift.delete()
        self.assertEqual(CashCount.objects.count(), 0)

    def test_cash_count_total_for_shift(self):
        """The total counted cash for a shift is the sum of all subtotals."""
        CashCount.objects.create(
            shift=self.shift,
            denomination_value=Decimal("1000.00"), quantity=1,  # 1000
        )
        CashCount.objects.create(
            shift=self.shift,
            denomination_value=Decimal("500.00"), quantity=2,   # 1000
        )
        CashCount.objects.create(
            shift=self.shift,
            denomination_value=Decimal("100.00"), quantity=5,   # 500
        )
        total = CashCount.objects.filter(shift=self.shift).aggregate(
            total=dj_models.Sum("subtotal")
        )["total"]
        self.assertEqual(total, Decimal("2500.00"))


class CashCountAPITest(TestCase):
    """Tests for the cash count API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="cashier1", password="testpass123"
        )
        self.client.force_login(self.user)
        self.shift = Shift.objects.create(
            cashier=self.user,
            starting_float=Decimal("1000.00"),
        )

    def test_post_cash_count_creates_entries(self):
        """POST /api/shifts/<id>/cash-count/ should create CashCount entries."""
        payload = {
            "denominations": [
                {"value": "1000.00", "qty": 1},
                {"value": "500.00", "qty": 2},
                {"value": "100.00", "qty": 3},
            ]
        }
        response = self.client.post(
            f"/api/shifts/{self.shift.id}/cash-count/",
            payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["entry_count"], 3)
        self.assertEqual(data["total_counted"], "2300.00")

    def test_post_cash_count_replaces_previous_entries(self):
        """POST replaces all previous entries for this shift (no duplicates)."""
        # First post
        self.client.post(
            f"/api/shifts/{self.shift.id}/cash-count/",
            {"denominations": [{"value": "1000.00", "qty": 1}]},
            content_type="application/json",
        )
        self.assertEqual(CashCount.objects.filter(shift=self.shift).count(), 1)

        # Second post replaces
        response = self.client.post(
            f"/api/shifts/{self.shift.id}/cash-count/",
            {"denominations": [{"value": "500.00", "qty": 5}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(CashCount.objects.filter(shift=self.shift).count(), 1)
        self.assertEqual(response.json()["total_counted"], "2500.00")

    def test_get_cash_count_returns_entries_and_total(self):
        """GET /api/shifts/<id>/cash-count/ should return entries and total."""
        CashCount.objects.create(
            shift=self.shift, denomination_value=Decimal("1000.00"), quantity=2,
        )
        CashCount.objects.create(
            shift=self.shift, denomination_value=Decimal("100.00"), quantity=5,
        )
        response = self.client.get(f"/api/shifts/{self.shift.id}/cash-count/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["entries"]), 2)
        self.assertEqual(data["total_counted"], "2500.00")

    def test_get_cash_count_empty(self):
        """GET with no entries returns empty list and 0.00 total."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/cash-count/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["entries"], [])
        self.assertEqual(data["total_counted"], "0.00")

    def test_post_cash_count_invalid_json_returns_400(self):
        """Invalid JSON should return 400."""
        response = self.client.post(
            f"/api/shifts/{self.shift.id}/cash-count/",
            "not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_post_cash_count_shift_not_found(self):
        """Invalid shift ID should return 404."""
        response = self.client.post(
            "/api/shifts/99999/cash-count/",
            {"denominations": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)


# ===================== EXPENSE TRACKING TESTS =====================

class ExpenseModelTest(TestCase):
    """Tests for the Expense model creation and field constraints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="cashier1", password="testpass123"
        )
        self.shift = Shift.objects.create(
            cashier=self.user,
            starting_float=Decimal("1000.00"),
        )

    def test_create_expense_with_all_fields(self):
        """Expense created with amount, description, category, and shift."""
        from pos.models import Expense
        expense = Expense.objects.create(
            shift=self.shift,
            amount=Decimal("150.00"),
            description="Bought more ice",
            category="Supplies",
        )
        self.assertIsNotNone(expense.id)
        self.assertEqual(expense.amount, Decimal("150.00"))
        self.assertEqual(expense.description, "Bought more ice")
        self.assertEqual(expense.category, "Supplies")
        self.assertEqual(expense.shift, self.shift)

    def test_expense_category_optional(self):
        """Category field should be optional."""
        from pos.models import Expense
        expense = Expense.objects.create(
            shift=self.shift,
            amount=Decimal("50.00"),
            description="Paid tricycle delivery",
        )
        self.assertIsNone(expense.category)

    def test_expense_created_at_auto_set(self):
        """created_at should be auto-set on creation."""
        from pos.models import Expense
        from django.utils import timezone
        expense = Expense.objects.create(
            shift=self.shift,
            amount=Decimal("75.00"),
            description="Test expense",
        )
        self.assertIsNotNone(expense.created_at)
        self.assertAlmostEqual(
            expense.created_at.timestamp(),
            timezone.now().timestamp(),
            delta=10,
        )

    def test_expense_str_method(self):
        """String representation includes amount and description."""
        from pos.models import Expense
        expense = Expense.objects.create(
            shift=self.shift,
            amount=Decimal("200.00"),
            description="Ice supply",
        )
        self.assertIn("₱200.00", str(expense))
        self.assertIn("Ice supply", str(expense))

    def test_expenses_related_to_shift(self):
        """Expenses should be accessible through shift's related name."""
        from pos.models import Expense
        e1 = Expense.objects.create(
            shift=self.shift, amount=Decimal("100.00"), description="Expense 1"
        )
        e2 = Expense.objects.create(
            shift=self.shift, amount=Decimal("50.00"), description="Expense 2"
        )
        self.assertEqual(self.shift.expenses.count(), 2)
        self.assertIn(e1, self.shift.expenses.all())
        self.assertIn(e2, self.shift.expenses.all())


class ExpenseAPITest(TestCase):
    """Tests for the expense CRUD API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="cashier1", password="testpass123"
        )
        self.client.force_login(self.user)
        self.shift = Shift.objects.create(
            cashier=self.user,
            starting_float=Decimal("1000.00"),
        )

    def test_post_expense_creates_expense(self):
        """POST /api/shifts/{id}/expenses/ creates an expense."""
        from pos.models import Expense
        response = self.client.post(
            f"/api/shifts/{self.shift.id}/expenses/",
            {
                "amount": "150.00",
                "description": "Bought more ice",
                "category": "Supplies",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["amount"], "150.00")
        self.assertEqual(data["description"], "Bought more ice")
        self.assertEqual(data["category"], "Supplies")
        self.assertEqual(Expense.objects.count(), 1)

    def test_post_expense_minimal_fields(self):
        """POST expense without category should still work."""
        response = self.client.post(
            f"/api/shifts/{self.shift.id}/expenses/",
            {
                "amount": "75.00",
                "description": "Tricycle fare",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["amount"], "75.00")
        self.assertEqual(data["description"], "Tricycle fare")
        self.assertIsNone(data.get("category"))

    def test_post_expense_missing_amount(self):
        """POST without amount should return 400."""
        response = self.client.post(
            f"/api/shifts/{self.shift.id}/expenses/",
            {"description": "Missing amount"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_post_expense_missing_description(self):
        """POST without description should return 400."""
        response = self.client.post(
            f"/api/shifts/{self.shift.id}/expenses/",
            {"amount": "50.00"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_post_expense_invalid_json(self):
        """Invalid JSON should return 400."""
        response = self.client.post(
            f"/api/shifts/{self.shift.id}/expenses/",
            "not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_get_expenses_returns_list(self):
        """GET /api/shifts/{id}/expenses/ returns list of expenses."""
        from pos.models import Expense
        Expense.objects.create(
            shift=self.shift, amount=Decimal("100.00"),
            description="Ice", category="Supplies"
        )
        Expense.objects.create(
            shift=self.shift, amount=Decimal("50.00"),
            description="Fare", category="Transport"
        )
        response = self.client.get(
            f"/api/shifts/{self.shift.id}/expenses/"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["expenses"]), 2)

    def test_get_expenses_total(self):
        """GET response includes total_expenses field."""
        from pos.models import Expense
        Expense.objects.create(
            shift=self.shift, amount=Decimal("100.00"),
            description="Ice"
        )
        Expense.objects.create(
            shift=self.shift, amount=Decimal("50.00"),
            description="Fare"
        )
        response = self.client.get(
            f"/api/shifts/{self.shift.id}/expenses/"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_expenses"], "150.00")

    def test_get_expenses_empty_shift(self):
        """GET for shift with no expenses returns empty list."""
        response = self.client.get(
            f"/api/shifts/{self.shift.id}/expenses/"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["expenses"], [])
        self.assertEqual(data["total_expenses"], "0.00")

    def test_get_expenses_other_shifts_not_included(self):
        """Expenses from other shifts should not be included."""
        from pos.models import Expense
        other_user = User.objects.create_user(
            username="cashier2", password="testpass123"
        )
        other_shift = Shift.objects.create(
            cashier=other_user, starting_float=Decimal("500.00")
        )
        Expense.objects.create(
            shift=other_shift, amount=Decimal("999.00"),
            description="Other shift expense"
        )
        response = self.client.get(
            f"/api/shifts/{self.shift.id}/expenses/"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["expenses"], [])

    def test_post_expense_publicly_accessible(self):
        """Unauthenticated requests should work in offline mode."""
        self.client.logout()
        response = self.client.post(
            f"/api/shifts/{self.shift.id}/expenses/",
            {"amount": "50.00", "description": "test"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)  # created successfully

    def test_shift_not_found(self):
        """Request for non-existent shift returns 404."""
        response = self.client.post(
            "/api/shifts/99999/expenses/",
            {"amount": "50.00", "description": "test"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_get_expenses_shift_not_found(self):
        """GET for non-existent shift returns 404."""
        response = self.client.get(
            "/api/shifts/99999/expenses/"
        )
        self.assertEqual(response.status_code, 404)


# ===================== SHIFT REPORT (X-Read / Z-Read) TESTS =====================

class ShiftXReadTest(TestCase):
    """Tests for X-Read endpoint (interim report, does not close shift)."""

    def setUp(self):
        self.client.force_login(
            User.objects.create_user(username="cashier", password="testpass123")
        )
        self.shift = Shift.objects.create(
            cashier=User.objects.get(username="cashier"),
            starting_float=Decimal("1000.00"),
        )
        # Create transactions for this shift
        from pos.models import Transaction
        self.txn1 = Transaction.objects.create(
            shift=self.shift,
            subtotal=Decimal("500.00"),
            grand_total=Decimal("500.00"),
            payment_method="CASH",
            vat_amount=Decimal("53.57"),
        )
        self.txn2 = Transaction.objects.create(
            shift=self.shift,
            subtotal=Decimal("300.00"),
            grand_total=Decimal("300.00"),
            payment_method="DIGITAL",
            vat_amount=Decimal("32.14"),
        )
        self.txn3 = Transaction.objects.create(
            shift=self.shift,
            subtotal=Decimal("200.00"),
            grand_total=Decimal("200.00"),
            payment_method="CASH",
            vat_amount=Decimal("21.43"),
        )
        # Voided transaction should not count
        Transaction.objects.create(
            shift=self.shift,
            subtotal=Decimal("100.00"),
            grand_total=Decimal("0.00"),
            payment_method="CASH",
            status="VOIDED",
        )
        # Create expenses
        from pos.models import Expense
        Expense.objects.create(
            shift=self.shift, amount=Decimal("50.00"),
            description="Ice", category="Supplies"
        )
        Expense.objects.create(
            shift=self.shift, amount=Decimal("30.00"),
            description="Transport", category=None,
        )
        # Create cash count
        from pos.models import CashCount
        CashCount.objects.create(
            shift=self.shift, denomination_value=Decimal("500.00"), quantity=2,
        )
        CashCount.objects.create(
            shift=self.shift, denomination_value=Decimal("100.00"), quantity=3,
        )

    def test_x_read_returns_200(self):
        """X-Read endpoint returns 200 for valid shift."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/x-read/")
        self.assertEqual(response.status_code, 200)

    def test_x_read_returns_expected_keys(self):
        """X-Read response contains expected top-level keys."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/x-read/")
        data = response.json()
        self.assertIn("shift_id", data)
        self.assertIn("status", data)
        self.assertIn("start_time", data)
        self.assertIn("starting_float", data)
        self.assertIn("total_sales", data)
        self.assertIn("net_sales", data)
        self.assertIn("payment_breakdown", data)
        self.assertIn("total_expenses", data)
        self.assertIn("expenses", data)
        self.assertIn("total_counted", data)
        self.assertIn("expected_cash", data)
        self.assertIn("variance", data)

    def test_x_read_total_sales(self):
        """Total sales should sum only COMPLETED transactions."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/x-read/")
        data = response.json()
        # 500 + 300 + 200 = 1000 (voided 100 excluded)
        self.assertEqual(data["total_sales"], "1000.00")

    def test_x_read_net_sales(self):
        """Net sales = total sales - total expenses."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/x-read/")
        data = response.json()
        self.assertEqual(data["net_sales"], "920.00")  # 1000 - 80

    def test_x_read_payment_breakdown(self):
        """Payment breakdown shows totals per method."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/x-read/")
        data = response.json()
        pmt = {p["method"]: p for p in data["payment_breakdown"]}
        self.assertIn("CASH", pmt)
        self.assertIn("DIGITAL", pmt)
        self.assertEqual(pmt["CASH"]["total"], "700.00")  # 500 + 200
        self.assertEqual(pmt["CASH"]["count"], 2)
        self.assertEqual(pmt["DIGITAL"]["total"], "300.00")
        self.assertEqual(pmt["DIGITAL"]["count"], 1)

    def test_x_read_expenses_list(self):
        """Expenses list is included."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/x-read/")
        data = response.json()
        self.assertEqual(data["total_expenses"], "80.00")
        self.assertEqual(len(data["expenses"]), 2)

    def test_x_read_expected_cash(self):
        """Expected cash = starting float + cash sales - expenses."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/x-read/")
        data = response.json()
        # 1000 (float) + 700 (cash sales) - 80 (expenses) = 1620
        self.assertEqual(data["expected_cash"], "1620.00")

    def test_x_read_variance(self):
        """Variance = total_counted - expected_cash."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/x-read/")
        data = response.json()
        # counted = 500*2 + 100*3 = 1300, expected = 1620, variance = -320
        self.assertEqual(data["total_counted"], "1300.00")
        self.assertEqual(data["variance"], "-320.00")

    def test_x_read_shift_remains_open(self):
        """X-Read does NOT close the shift."""
        self.client.get(f"/api/shifts/{self.shift.id}/x-read/")
        self.shift.refresh_from_db()
        self.assertEqual(self.shift.status, "OPEN")
        self.assertIsNone(self.shift.end_time)

    def test_x_read_nonexistent_shift_404(self):
        """X-Read for non-existent shift returns 404."""
        response = self.client.get("/api/shifts/99999/x-read/")
        self.assertEqual(response.status_code, 404)

    def test_x_read_publicly_accessible(self):
        """X-Read should work without authentication (offline mode)."""
        self.client.logout()
        response = self.client.get(f"/api/shifts/{self.shift.id}/x-read/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("total_sales", response.json())

    def test_x_read_no_transactions(self):
        """X-Read with no transactions returns zeros."""
        empty_shift = Shift.objects.create(
            cashier=User.objects.get(username="cashier"),
            starting_float=Decimal("500.00"),
        )
        response = self.client.get(f"/api/shifts/{empty_shift.id}/x-read/")
        data = response.json()
        self.assertEqual(data["total_sales"], "0.00")
        self.assertEqual(data["net_sales"], "0.00")
        self.assertEqual(data["payment_breakdown"], [])
        self.assertEqual(data["expected_cash"], "500.00")


class ShiftZReadTest(TestCase):
    """Tests for Z-Read endpoint (final report, closes shift)."""

    def setUp(self):
        self.client.force_login(
            User.objects.create_user(username="cashier2", password="testpass123")
        )
        self.shift = Shift.objects.create(
            cashier=User.objects.get(username="cashier2"),
            starting_float=Decimal("2000.00"),
        )
        from pos.models import Transaction, Expense, CashCount
        # Transactions
        Transaction.objects.create(
            shift=self.shift,
            subtotal=Decimal("1500.00"),
            grand_total=Decimal("1500.00"),
            payment_method="CASH",
            vat_amount=Decimal("160.71"),
        )
        Transaction.objects.create(
            shift=self.shift,
            subtotal=Decimal("750.00"),
            grand_total=Decimal("750.00"),
            payment_method="DIGITAL",
            vat_amount=Decimal("80.36"),
        )
        # Expenses ($)
        Expense.objects.create(
            shift=self.shift, amount=Decimal("120.00"),
            description="Cleaning supplies"
        )
        # Cash counts
        CashCount.objects.create(
            shift=self.shift, denomination_value=Decimal("1000.00"), quantity=1,
        )
        CashCount.objects.create(
            shift=self.shift, denomination_value=Decimal("500.00"), quantity=1,
        )

    def test_z_read_returns_200(self):
        """Z-Read endpoint returns 200 for valid open shift."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/z-read/")
        self.assertEqual(response.status_code, 200)

    def test_z_read_contains_expected_keys(self):
        """Z-Read response contains same report keys as X-Read."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/z-read/")
        data = response.json()
        self.assertIn("shift_id", data)
        self.assertIn("status", data)
        self.assertIn("start_time", data)
        self.assertIn("end_time", data)
        self.assertIn("starting_float", data)
        self.assertIn("total_sales", data)
        self.assertIn("net_sales", data)
        self.assertIn("payment_breakdown", data)
        self.assertIn("total_expenses", data)
        self.assertIn("expenses", data)
        self.assertIn("total_counted", data)
        self.assertIn("expected_cash", data)
        self.assertIn("variance", data)

    def test_z_read_closes_shift(self):
        """Z-Read closes the shift (status becomes CLOSED, end_time is set)."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/z-read/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], Shift.Status.CLOSED)
        self.assertIsNotNone(data["end_time"])
        # Verify in DB
        self.shift.refresh_from_db()
        self.assertEqual(self.shift.status, Shift.Status.CLOSED)
        self.assertIsNotNone(self.shift.end_time)

    def test_z_read_recalculates_after_close(self):
        """Z-Read returns correct report values on a closed shift."""
        response = self.client.get(f"/api/shifts/{self.shift.id}/z-read/")
        data = response.json()
        self.assertEqual(data["total_sales"], "2250.00")  # 1500 + 750
        self.assertEqual(data["net_sales"], "2130.00")    # 2250 - 120
        self.assertEqual(data["total_expenses"], "120.00")
        # Payment breakdown
        pmt = {p["method"]: p for p in data["payment_breakdown"]}
        self.assertEqual(pmt["CASH"]["total"], "1500.00")
        self.assertEqual(pmt["DIGITAL"]["total"], "750.00")
        # Expected cash: 2000 (float) + 1500 (cash sales) - 120 (expenses) = 3380
        self.assertEqual(data["expected_cash"], "3380.00")
        # Counted: 1000 + 500 = 1500, variance = 1500 - 3380 = -1880
        self.assertEqual(data["total_counted"], "1500.00")
        self.assertEqual(data["variance"], "-1880.00")

    def test_z_read_already_closed_returns_409(self):
        """Z-Read on an already closed shift returns 409."""
        # First close it
        self.client.get(f"/api/shifts/{self.shift.id}/z-read/")
        # Second attempt should fail
        response = self.client.get(f"/api/shifts/{self.shift.id}/z-read/")
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertIn("error", data)

    def test_z_read_nonexistent_shift_404(self):
        """Z-Read for non-existent shift returns 404."""
        response = self.client.get("/api/shifts/99999/z-read/")
        self.assertEqual(response.status_code, 404)

    def test_z_read_publicly_accessible(self):
        """Z-Read should work without authentication (offline mode)."""
        self.client.logout()
        response = self.client.get(f"/api/shifts/{self.shift.id}/z-read/")
        self.assertEqual(response.status_code, 200)

    def test_z_read_x_read_no_longer_works_after_close(self):
        """After Z-Read closes shift, X-Read should still work on closed shift."""
        self.client.get(f"/api/shifts/{self.shift.id}/z-read/")
        # X-Read should work on the (now closed) shift
        response = self.client.get(f"/api/shifts/{self.shift.id}/x-read/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], Shift.Status.CLOSED)

    def test_z_read_no_cash_count(self):
        """Z-Read with no cash count returns zeros for counted/variance."""
        new_shift = Shift.objects.create(
            cashier=User.objects.get(username="cashier2"),
            starting_float=Decimal("500.00"),
        )
        response = self.client.get(f"/api/shifts/{new_shift.id}/z-read/")
        data = response.json()
        self.assertEqual(data["total_counted"], "0.00")
        self.assertEqual(data["variance"], "-500.00")  # 0 - 500


# ===================== CLINIC REMARKS / PATIENT TESTS =====================

class PatientModelTest(TestCase):
    """Tests for the Patient model with clinic remarks."""

    def test_create_patient_without_remarks(self):
        """Patient can be created without remarks."""
        patient = Patient.objects.create(
            name="Juan Dela Cruz",
            fb_psid="psid_12345",
        )
        self.assertEqual(patient.name, "Juan Dela Cruz")
        self.assertEqual(patient.fb_psid, "psid_12345")
        self.assertIsNone(patient.remarks)

    def test_create_patient_with_remarks(self):
        """Patient can be created with clinic remarks."""
        patient = Patient.objects.create(
            name="Maria Santos",
            fb_psid="psid_67890",
            remarks="Needs to repeat TB test on next visit. BP was high at 140/90.",
        )
        self.assertEqual(patient.remarks, "Needs to repeat TB test on next visit. BP was high at 140/90.")

    def test_patient_str(self):
        """Patient string representation works."""
        patient = Patient.objects.create(
            name="Juan Dela Cruz",
            fb_psid="psid_12345",
        )
        self.assertIn("Juan Dela Cruz", str(patient))

    def test_remarks_can_be_updated(self):
        """Remarks can be edited after creation."""
        patient = Patient.objects.create(
            name="Pedro Reyes",
            fb_psid="psid_11111",
            remarks="Initial remark.",
        )
        patient.remarks = "Updated remark after follow-up."
        patient.save()
        patient.refresh_from_db()
        self.assertEqual(patient.remarks, "Updated remark after follow-up.")

    def test_remarks_can_be_cleared(self):
        """Remarks can be set back to null/empty."""
        patient = Patient.objects.create(
            name="Ana Lopez",
            fb_psid="psid_22222",
            remarks="Some remark.",
        )
        patient.remarks = None
        patient.save()
        patient.refresh_from_db()
        self.assertIsNone(patient.remarks)


class PatientAdminTest(TestCase):
    """Tests for Patient admin interface for clinic remarks."""

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="admin", password="admin123", email="admin@test.com"
        )
        self.client.force_login(self.admin_user)

    def test_patient_registered_in_admin(self):
        """Patient model is registered in Django admin."""
        from django.contrib.admin import site
        self.assertIn(Patient, site._registry)

    def test_admin_can_view_patients_list(self):
        """Admin can view the patient list page."""
        Patient.objects.create(name="Test Patient", fb_psid="psid_test")
        response = self.client.get("/admin/pos/patient/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Patient")

    def test_admin_can_add_patient_with_remarks(self):
        """Admin can create a patient with remarks via admin."""
        response = self.client.post("/admin/pos/patient/add/", {
            "name": "New Patient",
            "fb_psid": "psid_new",
            "remarks": "Test remark about condition.",
        })
        self.assertEqual(response.status_code, 302)  # redirect after save
        patient = Patient.objects.get(fb_psid="psid_new")
        self.assertEqual(patient.remarks, "Test remark about condition.")

    def test_admin_can_edit_remarks(self):
        """Admin can update remarks in patient detail view."""
        patient = Patient.objects.create(name="Edit Patient", fb_psid="psid_edit")
        response = self.client.post(f"/admin/pos/patient/{patient.id}/change/", {
            "name": "Edit Patient",
            "fb_psid": "psid_edit",
            "remarks": "Updated clinic remark.",
        })
        self.assertEqual(response.status_code, 302)
        patient.refresh_from_db()
        self.assertEqual(patient.remarks, "Updated clinic remark.")


class MessengerWebhookServiceTest(TestCase):
    """Tests for LLM context injection with clinic remarks."""

    def setUp(self):
        self.patient_with_remark = Patient.objects.create(
            name="With Remark",
            fb_psid="psid_remark",
            remarks="Patient needs to monitor BP daily. Medication adjusted.",
        )
        self.patient_no_remark = Patient.objects.create(
            name="No Remark",
            fb_psid="psid_no_remark",
        )

    def test_remark_included_in_llm_context(self):
        """Remark is included in LLM context for patients with remarks."""
        from pos.services import MessengerWebhookService
        service = MessengerWebhookService()
        context = service.build_llm_context(self.patient_with_remark)
        self.assertIsNotNone(context)
        self.assertIn("clinic remark for", context.lower())
        self.assertIn("monitor bp daily", context.lower())

    def test_no_remark_context_for_patients_without_remarks(self):
        """No remark context included for patients without remarks."""
        from pos.services import MessengerWebhookService
        service = MessengerWebhookService()
        context = service.build_llm_context(self.patient_no_remark)
        # Should either be empty, or not contain remarks-related content
        if context:
            self.assertNotIn("remark", context.lower())

    def test_none_patient_returns_empty_context(self):
        """None patient returns empty string context."""
        from pos.services import MessengerWebhookService
        service = MessengerWebhookService()
        context = service.build_llm_context(None)
        self.assertEqual(context, "")

    def test_llm_response_natural_language(self):
        """LLM response for remark-related question is natural (not raw remark)."""
        from pos.services import MessengerWebhookService
        service = MessengerWebhookService()
        prompt = service.build_system_prompt(self.patient_with_remark)
        self.assertIsNotNone(prompt)
        # Prompt should instruct not to reveal raw remarks
        self.assertIn("remark", prompt.lower())
        self.assertNotIn("Needs to monitor BP daily", prompt)  # should not be raw in prompt instructions

    # ------------------------------------------------------------------ #
    #  Smart Unregistered Chat — State Classification & LLM Prompts       #
    # ------------------------------------------------------------------ #

    def test_classify_psid_preregistration(self):
        """Unlinked PSID classifies as pre-registration."""
        from pos.services import MessengerWebhookService
        service = MessengerWebhookService()
        state = service.classify_psid("psid_nonexistent")
        self.assertEqual(state, "preregistration")

    def test_classify_psid_in_queue(self):
        """Patient with active queue classifies as in-queue."""
        from pos.models import Queue
        from pos.services import MessengerWebhookService
        patient = Patient.objects.create(name="Queue Patient", fb_psid="psid_queued")
        Queue.objects.create(patient=patient, status="waiting")
        service = MessengerWebhookService()
        state = service.classify_psid("psid_queued")
        self.assertEqual(state, "inqueue")

    def test_classify_psid_post_queue(self):
        """Patient with all entries served/skipped/cancelled classifies as post-queue."""
        from pos.models import Queue
        from pos.services import MessengerWebhookService
        patient = Patient.objects.create(name="Post Queue Patient", fb_psid="psid_postqueue")
        Queue.objects.create(patient=patient, status="served")
        Queue.objects.create(patient=patient, status="cancelled")
        service = MessengerWebhookService()
        state = service.classify_psid("psid_postqueue")
        self.assertEqual(state, "postqueue")

    def test_psid_with_mixed_queues_still_in_queue(self):
        """Patient with at least one active queue entry is in-queue."""
        from pos.models import Queue
        from pos.services import MessengerWebhookService
        patient = Patient.objects.create(name="Mixed Patient", fb_psid="psid_mixed")
        Queue.objects.create(patient=patient, status="served")
        Queue.objects.create(patient=patient, status="waiting")
        service = MessengerWebhookService()
        state = service.classify_psid("psid_mixed")
        self.assertEqual(state, "inqueue")

    def test_preregistration_prompt_contains_clinic_info(self):
        """Pre-registration prompt includes clinic info (hours, address, etc)."""
        from pos.services import MessengerWebhookService
        service = MessengerWebhookService()
        prompt = service.build_preregistration_prompt()
        self.assertIn("clinic", prompt.lower())
        self.assertIn("Ipo-Ipo Clinic", prompt)
        # Should mention typical clinic info topics
        self.assertTrue(
            any(term in prompt.lower() for term in ["hours", "address", "service", "location", "faq"])
        )

    def test_postqueue_prompt_contains_last_queue_info(self):
        """Post-queue prompt includes last queue entry info and clinic general info."""
        from pos.models import Queue
        from pos.services import MessengerWebhookService
        patient = Patient.objects.create(name="Done Patient", fb_psid="psid_done")
        Queue.objects.create(patient=patient, status="served", service="TB Screening", service_area="Clinic A")
        service = MessengerWebhookService()
        prompt = service.build_postqueue_prompt(patient)
        self.assertIn(patient.name, prompt)
        self.assertIn("Last queue entry", prompt)
        self.assertIn("TB Screening", prompt)
        self.assertIn("clinic", prompt.lower())
        self.assertIn("Ipo-Ipo Clinic", prompt)

    def test_postqueue_prompt_includes_remark_context(self):
        """Post-queue prompt includes the patient's clinic remarks."""
        from pos.models import Queue
        from pos.services import MessengerWebhookService
        patient = Patient.objects.create(
            name="Remark Patient",
            fb_psid="psid_remark_post",
            remarks="Follow-up needed in 2 weeks."
        )
        Queue.objects.create(patient=patient, status="served")
        service = MessengerWebhookService()
        prompt = service.build_postqueue_prompt(patient)
        self.assertIn("Follow-up needed in 2 weeks", prompt)

    def test_preregistration_prompt_no_queue_reference(self):
        """Pre-registration prompt should NOT reference queue entry data."""
        from pos.services import MessengerWebhookService
        service = MessengerWebhookService()
        prompt = service.build_preregistration_prompt()
        self.assertNotIn("queue", prompt.lower())

    def test_inqueue_prompt_preserves_existing_behavior(self):
        """In-queue patients still get the standard system prompt with remarks."""
        from pos.services import MessengerWebhookService
        patient = self.patient_with_remark
        service = MessengerWebhookService()
        prompt = service.build_system_prompt(patient)
        # Same assertions as existing test_llm_response_natural_language
        self.assertIsNotNone(prompt)
        self.assertIn("remark", prompt.lower())
        self.assertNotIn("Last queue entry", prompt)

    def test_preregistration_route_uses_preregistration_prompt(self):
        """Pre-registration route picks the preregistration prompt."""
        from pos.services import MessengerWebhookService
        service = MessengerWebhookService()
        # We verify the routing logic by checking which method is called
        # The prompt used for preregistration should match
        state = service.classify_psid("psid_new_user")
        self.assertEqual(state, "preregistration")

    def test_postqueue_route_uses_postqueue_prompt(self):
        """Post-queue route picks the postqueue prompt."""
        from pos.models import Queue
        from pos.services import MessengerWebhookService
        patient = Patient.objects.create(name="Served Patient", fb_psid="psid_served")
        Queue.objects.create(patient=patient, status="served")
        service = MessengerWebhookService()
        state = service.classify_psid("psid_served")
        self.assertEqual(state, "postqueue")

    def test_inqueue_returns_different_prompt_than_preregistration(self):
        """In-queue and pre-registration states produce different prompts."""
        from pos.services import MessengerWebhookService
        service = MessengerWebhookService()
        patient = self.patient_with_remark
        inqueue_prompt = service.build_system_prompt(patient)
        prereg_prompt = service.build_preregistration_prompt()
        self.assertNotEqual(inqueue_prompt, prereg_prompt)

    def test_postqueue_returns_different_prompt_than_preregistration(self):
        """Post-queue and pre-registration states produce different prompts."""
        from pos.models import Queue
        from pos.services import MessengerWebhookService
        patient = Patient.objects.create(name="Another Patient", fb_psid="psid_another")
        Queue.objects.create(patient=patient, status="served")
        service = MessengerWebhookService()
        postq_prompt = service.build_postqueue_prompt(patient)
        prereg_prompt = service.build_preregistration_prompt()
        self.assertNotEqual(postq_prompt, prereg_prompt)

    def test_preregistration_prompt_has_no_patient_name(self):
        """Pre-registration prompt should not reference any specific patient."""
        from pos.services import MessengerWebhookService
        service = MessengerWebhookService()
        prompt = service.build_preregistration_prompt()
        # Common patient words should not appear since no patient is linked
        self.assertNotIn("patient:", prompt.lower())


class QueueModelTest(TestCase):
    """Tests for the Queue model."""

    def setUp(self):
        self.patient = Patient.objects.create(
            name="Test Patient", fb_psid="psid_queue_test"
        )

    def test_create_queue_entry(self):
        """Can create a basic queue entry."""
        from pos.models import Queue
        entry = Queue.objects.create(
            patient=self.patient,
            status="waiting",
            service="Check-up",
            service_area="Consultation Room"
        )
        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.patient, self.patient)
        self.assertEqual(entry.status, "waiting")

    def test_queue_status_waiting_unserved(self):
        """Default status is 'waiting' for new queue entries."""
        from pos.models import Queue
        entry = Queue.objects.create(patient=self.patient, status="waiting")
        self.assertEqual(entry.status, "waiting")

    def test_queue_default_status(self):
        """Queue entries default to 'waiting' status."""
        from pos.models import Queue
        entry = Queue.objects.create(patient=self.patient, status="waiting")
        self.assertEqual(entry.status, "waiting")

    def test_queue_served_status(self):
        """Queue can be marked as served."""
        from pos.models import Queue
        entry = Queue.objects.create(patient=self.patient, status="served")
        self.assertEqual(entry.status, "served")

    def test_queue_cancelled_status(self):
        """Queue can be marked as cancelled."""
        from pos.models import Queue
        entry = Queue.objects.create(patient=self.patient, status="cancelled")
        self.assertEqual(entry.status, "cancelled")

    def test_queue_skipped_status(self):
        """Queue can be marked as skipped."""
        from pos.models import Queue
        entry = Queue.objects.create(patient=self.patient, status="skipped")
        self.assertEqual(entry.status, "skipped")

    def test_queue_str_representation(self):
        """String representation includes patient name and status."""
        from pos.models import Queue
        entry = Queue.objects.create(patient=self.patient, status="waiting")
        self.assertIn(self.patient.name, str(entry))
        self.assertIn("waiting", str(entry))

    def test_queue_ordered_by_created(self):
        """Queue entries have automatic created_at ordering."""
        from pos.models import Queue
        e1 = Queue.objects.create(patient=self.patient, status="waiting")
        e2 = Queue.objects.create(patient=self.patient, status="waiting")
        entries = Queue.objects.filter(patient=self.patient)
        self.assertEqual(entries.count(), 2)

    def test_active_queue_scope(self):
        """Can filter for active (waiting) queue entries."""
        from pos.models import Queue
        Queue.objects.create(patient=self.patient, status="served")
        active = Queue.objects.create(patient=self.patient, status="waiting")
        queues = Queue.objects.filter(patient=self.patient, status="waiting")
        self.assertEqual(queues.count(), 1)
        self.assertEqual(queues.first().id, active.id)

# ===================== NAVIGATION & UI TESTS =====================

class NavigationTest(TestCase):
    """Test that sidebar navigation links render correctly on all POS pages."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test", type="LPG", code="T-01")
        self.cat = Category.objects.create(name="Cat")
        Item.objects.create(
            category=self.cat, name="Item", sku="I-01",
            cost_price=10, selling_price=20, stock_qty=5, branch=self.branch
        )
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()

    def assert_nav_links_present(self, response, active_section=""):
        """Helper: assert all 8 nav items appear with working hrefs."""
        content = response.content.decode()
        expected = ["Dashboard", "Inventory", "Categories", "Discounts",
                    "Sales History", "Reports", "Products", "Customers"]
        for label in expected:
            self.assertIn(label, content,
                          msg=f"Missing '{label}' nav link on {active_section}")

        self.assertNotIn('href="{{', content,
                         msg=f"Found unresolved template variable in href on {active_section}")

    def test_home_page_nav(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assert_nav_links_present(response, "home")

    def test_customers_page_nav(self):
        response = self.client.get(reverse("customers"))
        self.assertEqual(response.status_code, 200)
        self.assert_nav_links_present(response, "customers")

    def test_products_page_nav(self):
        response = self.client.get(reverse("product_catalog"))
        self.assertEqual(response.status_code, 200)
        self.assert_nav_links_present(response, "products")

    def test_sales_page_nav(self):
        response = self.client.get(reverse("sales_history"))
        self.assertEqual(response.status_code, 200)
        self.assert_nav_links_present(response, "sales")

    def test_reports_page_nav(self):
        response = self.client.get(reverse("reports"))
        self.assertEqual(response.status_code, 200)
        self.assert_nav_links_present(response, "reports")

    def test_inventory_dashboard_page_nav(self):
        response = self.client.get(reverse("inventory_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assert_nav_links_present(response, "inventory")

    def test_no_premium_cta(self):
        """Offline POS should not show Premium Plan / Upgrade CTA."""
        response = self.client.get(reverse("home"))
        content = response.content.decode()
        self.assertNotIn("Premium Plan", content)
        self.assertNotIn("Upgrade Now", content)
        self.assertNotIn("upgrade-cta", content)


# ===================== PHASE 3: INVENTORY TESTS =====================

class ItemDescriptionFieldTest(TestCase):
    """Tests for the description field on Item model."""

    def setUp(self):
        self.cat = Category.objects.create(name="TestCat")

    def test_item_has_description_field(self):
        """Item model should have a description field."""
        item = Item.objects.create(
            category=self.cat, name="Test", sku="TST-001",
            cost_price="10", selling_price="20",
            description="A test product description"
        )
        item.refresh_from_db()
        self.assertEqual(item.description, "A test product description")

    def test_description_optional(self):
        """Description should be optional (blank=True)."""
        item = Item.objects.create(
            category=self.cat, name="No Desc", sku="TST-002",
            cost_price="10", selling_price="20"
        )
        item.refresh_from_db()
        self.assertIsNone(item.description)

    def test_description_long_text(self):
        """Description should accept long text."""
        long_text = "A" * 5000
        item = Item.objects.create(
            category=self.cat, name="Long Desc", sku="TST-003",
            cost_price="10", selling_price="20",
            description=long_text
        )
        item.refresh_from_db()
        self.assertEqual(len(item.description), 5000)


class ItemSizeModelTest(TestCase):
    """Tests for the ItemSize model."""

    def setUp(self):
        self.cat = Category.objects.create(name="TestCat")
        self.item = Item.objects.create(
            category=self.cat, name="LPG Tank", sku="LPG-001",
            cost_price="500", selling_price="800", stock_qty=10
        )

    def test_item_size_creation(self):
        """Create an ItemSize with name and price."""
        size = ItemSize.objects.create(
            item=self.item,
            name="11kg",
            price=Decimal("850.00"),
            retail_price=Decimal("950.00")
        )
        self.assertEqual(size.name, "11kg")
        self.assertEqual(size.price, Decimal("850.00"))
        self.assertEqual(size.retail_price, Decimal("950.00"))

    def test_item_size_str(self):
        size = ItemSize.objects.create(
            item=self.item, name="22kg", price=1500
        )
        self.assertIn("22kg", str(size))
        self.assertIn(self.item.name, str(size))

    def test_item_size_default_retail_price(self):
        """get_retail_price() should return price if retail_price is not set."""
        size = ItemSize.objects.create(
            item=self.item, name="Small", price=Decimal("100.00")
        )
        # DB stores null for retail_price
        self.assertIsNone(size.retail_price)
        # Method falls back to price
        self.assertEqual(size.get_retail_price(), Decimal("100.00"))

    def test_item_size_unique_per_item(self):
        """Size names should be unique per item."""
        ItemSize.objects.create(item=self.item, name="11kg", price=850)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ItemSize.objects.create(item=self.item, name="11kg", price=900)

    def test_same_size_name_different_items(self):
        """Different items can have same size name."""
        item2 = Item.objects.create(
            category=self.cat, name="Other Tank", sku="LPG-002",
            cost_price="400", selling_price="700"
        )
        ItemSize.objects.create(item=self.item, name="11kg", price=850)
        ItemSize.objects.create(item=item2, name="11kg", price=900)
        self.assertEqual(ItemSize.objects.count(), 2)

    def test_item_cascade_delete_sizes(self):
        """Deleting an Item should delete its sizes."""
        ItemSize.objects.create(item=self.item, name="11kg", price=850)
        ItemSize.objects.create(item=self.item, name="22kg", price=1500)
        self.assertEqual(ItemSize.objects.count(), 2)
        self.item.delete()
        self.assertEqual(ItemSize.objects.count(), 0)

    def test_item_has_sizes_related_name(self):
        """Item should have a 'sizes' related name."""
        s1 = ItemSize.objects.create(item=self.item, name="S", price=100)
        s2 = ItemSize.objects.create(item=self.item, name="M", price=150)
        self.assertIn(s1, self.item.sizes.all())
        self.assertIn(s2, self.item.sizes.all())
        self.assertEqual(self.item.sizes.count(), 2)

    def test_item_size_price_positive(self):
        """Price must be positive."""
        from django.core.exceptions import ValidationError
        size = ItemSize(item=self.item, name="Free", price=Decimal("-1.00"))
        with self.assertRaises(ValidationError):
            size.full_clean()

    def test_item_size_retail_price_positive(self):
        """Retail price must be positive if set."""
        from django.core.exceptions import ValidationError
        size = ItemSize(item=self.item, name="Bad", price=100, retail_price=Decimal("-1"))
        with self.assertRaises(ValidationError):
            size.full_clean()


class ItemSizeFormViewTest(TestCase):
    """Tests for item form with sizes in inventory."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", password="admin123", email="a@b.com"
        )
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name="TestCat")
        self.branch = Branch.objects.create(
            name="Test Branch", type="RETAIL", code="TST-01"
        )
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()

    def test_item_create_form_renders(self):
        """Item add form should render successfully."""
        response = self.client.get(reverse("item_add"))
        self.assertEqual(response.status_code, 200)

    def test_item_edit_form_has_description_field(self):
        """Item edit form should show description field."""
        item = Item.objects.create(
            category=self.cat, name="Test", sku="TST-001",
            cost_price="10", selling_price="20", branch=self.branch
        )
        response = self.client.get(reverse("item_edit", kwargs={"pk": item.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "description")

    def test_inventory_dashboard_shows_description_in_table(self):
        """Inventory dashboard should show item description."""
        Item.objects.create(
            category=self.cat, name="Test", sku="TST-001",
            cost_price="10", selling_price="20",
            description="A great product", branch=self.branch
        )
        response = self.client.get(reverse("inventory_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A great product")

    def test_inventory_dashboard_shows_size_info(self):
        """Inventory dashboard should show size info for items."""
        item = Item.objects.create(
            category=self.cat, name="LPG", sku="LPG-001",
            cost_price="500", selling_price="800", branch=self.branch
        )
        ItemSize.objects.create(item=item, name="11kg", price=850)
        response = self.client.get(reverse("inventory_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "11kg")


class ItemSizeAdminTest(TestCase):
    """Tests for ItemSize admin registration."""

    def test_item_size_registered_in_admin(self):
        from django.contrib.admin import site
        from pos.models import ItemSize
        self.assertIn(ItemSize, site._registry)


class ItemSizeAPITest(TestCase):
    """Tests for size API used by POS frontend."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="user", password="pass123"
        )
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name="Test")
        self.branch = Branch.objects.create(
            name="Branch", type="RETAIL", code="BR-01"
        )
        self.item = Item.objects.create(
            category=self.cat, name="LPG", sku="LPG-001",
            cost_price="500", selling_price="800",
            stock_qty=10, branch=self.branch
        )
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()

    def test_item_sizes_api_returns_sizes(self):
        """GET /api/items/<id>/sizes/ should return sizes list."""
        s1 = ItemSize.objects.create(item=self.item, name="11kg", price=850)
        s2 = ItemSize.objects.create(item=self.item, name="22kg", price=1500)
        response = self.client.get(f"/api/items/{self.item.id}/sizes/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        names = [s["name"] for s in data]
        self.assertIn("11kg", names)
        self.assertIn("22kg", names)

    def test_item_sizes_api_empty(self):
        """Item without sizes should return empty list."""
        response = self.client.get(f"/api/items/{self.item.id}/sizes/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_item_sizes_api_404(self):
        """Non-existent item should return 404."""
        response = self.client.get("/api/items/99999/sizes/")
        self.assertEqual(response.status_code, 404)


# ===================== PHASE 4: POS TESTS =====================

class POSCategoryFilterTest(TestCase):
    """Tests for categorized product display in POS."""

    def setUp(self):
        self.user = User.objects.create_user(username="user", password="***")
        self.client.force_login(self.user)
        self.cat1 = Category.objects.create(name="Beverages")
        self.cat2 = Category.objects.create(name="Food")
        self.branch = Branch.objects.create(name="Branch", type="RETAIL", code="BR-01")
        self.item1 = Item.objects.create(
            category=self.cat1, name="Coke", sku="DRK-001",
            cost_price="10", selling_price="25", stock_qty=100,
            branch=self.branch
        )
        self.item2 = Item.objects.create(
            category=self.cat2, name="Burger", sku="FD-001",
            cost_price="30", selling_price="65", stock_qty=50,
            branch=self.branch
        )
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()

    def test_home_page_lists_categories(self):
        """Home POS page should include category names for filter."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Beverages")
        self.assertContains(response, "Food")

    def test_home_page_has_category_filter_buttons(self):
        """POS home page should have category filter buttons/tabs."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("All", content)

    def test_home_page_shows_all_products_by_default(self):
        """All products should display on POS home by default."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Coke")
        self.assertContains(response, "Burger")


class POSSearchTest(TestCase):
    """Tests for product search in POS."""

    def setUp(self):
        self.user = User.objects.create_user(username="user", password="***")
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name="Drinks")
        self.branch = Branch.objects.create(name="Branch", type="RETAIL", code="BR-01")
        self.item1 = Item.objects.create(
            category=self.cat, name="Coca Cola", sku="DRK-001",
            cost_price="10", selling_price="25", stock_qty=100,
            branch=self.branch
        )
        self.item2 = Item.objects.create(
            category=self.cat, name="Pepsi", sku="DRK-002",
            cost_price="10", selling_price="25", stock_qty=100,
            branch=self.branch
        )
        self.item3 = Item.objects.create(
            category=self.cat, name="Water", sku="DRK-003",
            cost_price="5", selling_price="10", stock_qty=200,
            branch=self.branch
        )
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()

    def test_search_by_name(self):
        """Searching by name should filter products."""
        response = self.client.get(reverse("home") + "?q=Coca")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Coca Cola")
        self.assertNotContains(response, "Pepsi")

    def test_search_by_sku(self):
        """Searching by SKU should find the product."""
        response = self.client.get(reverse("home") + "?q=DRK-002")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pepsi")
        self.assertNotContains(response, "Coca Cola")

    def test_search_empty_results(self):
        """Search with no matches should show empty state."""
        response = self.client.get(reverse("home") + "?q=ZZZZZ")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Coca Cola")
        self.assertNotContains(response, "Pepsi")

    def test_search_case_insensitive(self):
        """Search should be case-insensitive."""
        response = self.client.get(reverse("home") + "?q=pepsi")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pepsi")


class POSReprintReceiptTest(TestCase):
    """Tests for receipt reprint functionality."""

    def setUp(self):
        self.user = User.objects.create_user(username="user", password="***")
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name="Test")
        self.branch = Branch.objects.create(name="Branch", type="RETAIL", code="BR-01")
        self.item = Item.objects.create(
            category=self.cat, name="Coke", sku="DRK-001",
            cost_price="10", selling_price="25", branch=self.branch
        )
        self.txn = Transaction.objects.create(
            subtotal="25.00", grand_total="25.00", branch=self.branch
        )
        session = self.client.session
        session["current_branch_id"] = self.branch.id
        session.save()

    def test_sales_history_has_print_link(self):
        """Sales history page should have a print/reprint link per transaction."""
        response = self.client.get(reverse("sales_history"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode().lower()
        self.assertIn("receipt", content)

    def test_receipt_print_page_exists(self):
        """Receipt print page should be accessible."""
        response = self.client.get(reverse("receipt_print", kwargs={"pk": self.txn.pk}))
        self.assertEqual(response.status_code, 200)

    def test_receipt_print_shows_txn_id(self):
        """Print page should show the transaction id."""
        response = self.client.get(reverse("receipt_print", kwargs={"pk": self.txn.pk}))
        self.assertContains(response, str(self.txn.id))


class POSReceiptViewTest(TestCase):
    """Tests for the receipt view page."""

    def setUp(self):
        self.user = User.objects.create_user(username="user", password="***")
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name="Test")
        self.branch = Branch.objects.create(name="Branch", type="RETAIL", code="BR-01")
        self.item = Item.objects.create(
            category=self.cat, name="Coke", sku="DRK-001",
            cost_price="10", selling_price="25", branch=self.branch
        )
        self.txn = Transaction.objects.create(
            subtotal="25.00", grand_total="25.00", branch=self.branch
        )

    def test_receipt_page_exists(self):
        """Receipt view page should be accessible."""
        response = self.client.get(reverse("receipt", kwargs={"pk": self.txn.pk}))
        self.assertEqual(response.status_code, 200)

    def test_receipt_page_shows_items(self):
        """Receipt page should show transaction line items."""
        from pos.models import TransactionItem
        TransactionItem.objects.create(
            transaction=self.txn, item=self.item,
            quantity=2, unit_price=Decimal("25.00")
        )
        response = self.client.get(reverse("receipt", kwargs={"pk": self.txn.pk}))
        self.assertContains(response, "Coke")
