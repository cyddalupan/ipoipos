"""Tests for Ipo-Ipo POS — TDD approach."""

from django.test import TestCase, Client
from django.urls import reverse, resolve
from decimal import Decimal, ROUND_HALF_UP
import json

from pos.models import Category, Item, DiscountType, Transaction, TransactionItem


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


# ===================== VIEW / URL TEST =====================

class UrlRoutingTest(TestCase):
    """Ensure all sidebar nav items resolve to real views."""

    def test_home_url_resolves(self):
        resolver = resolve("/")
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

    def test_checkout_api_url_resolves(self):
        resolver = resolve("/api/checkout/")
        self.assertEqual(resolver.url_name, "checkout_api")


class ViewSmokeTest(TestCase):
    """Quick smoke tests — views return 200."""

    def setUp(self):
        self.client = Client()
        self.cat = Category.objects.create(name="Test")
        self.item = Item.objects.create(
            category=self.cat, name="Test", sku="TST-001",
            emoji="🧪", cost_price=50, selling_price=100, stock_qty=10
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
                            emoji="❌", cost_price=10, selling_price=20, stock_qty=5, is_active=False)
        r = self.client.get(reverse("home"))
        names = [i.name for i in r.context["items"]]
        self.assertNotIn("Inactive", names)
        self.assertIn("Test", names)  # Test is the setUp item which is active

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
            status="COMPLETED"
        )
        txn2 = Transaction.objects.create(
            subtotal="100.00", grand_total="100.00", payment_method="GCASH",
            status="COMPLETED"
        )
        # A voided transaction should not count
        Transaction.objects.create(
            subtotal="50.00", grand_total="0.00", status="VOIDED"
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
                            stock_qty=3, low_stock_threshold=10)
        # This item is fine (threshold=10, stock=50)
        Item.objects.create(category=cat, name="Well Stocked", sku="FUL-001",
                            emoji="✅", cost_price=10, selling_price=20,
                            stock_qty=50, low_stock_threshold=10)
        r = self.client.get(reverse("home"))
        # Setup item (Test: stock=10, threshold=10) + Low Stock Item = 2
        self.assertEqual(r.context["low_stock_count"], 2)

    def test_low_stock_item_inactive_not_counted(self):
        """Inactive items are not counted even if low stock."""
        cat = Category.objects.create(name="Extra")
        Item.objects.create(category=cat, name="Inactive Low", sku="I-LOW-001",
                            emoji="💤", cost_price=10, selling_price=20,
                            stock_qty=0, low_stock_threshold=10, is_active=False)
        r = self.client.get(reverse("home"))
        # Setup item (Test: stock=10, threshold=10) is still counted
        self.assertEqual(r.context["low_stock_count"], 1)

    def test_home_search_filter_by_name(self):
        """Home ?q=term filters items by name (case-insensitive)."""
        cat = Category.objects.create(name="Extra")
        Item.objects.create(category=cat, name="Burger Supreme", sku="BUR-001",
                            emoji="🍔", cost_price=50, selling_price=100, stock_qty=10)
        Item.objects.create(category=cat, name="Fries Large", sku="FRI-001",
                            emoji="🍟", cost_price=20, selling_price=45, stock_qty=20)
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
        txn1 = Transaction.objects.create(subtotal="100", grand_total="100", status="COMPLETED")
        Transaction.objects.create(subtotal="50", grand_total="0", status="VOIDED")
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

    def test_inventory_edit_200(self):
        r = self.client.get(reverse("item_edit", args=[self.item.pk]))
        self.assertEqual(r.status_code, 200)

    def test_receipt_200(self):
        txn = Transaction.objects.create(subtotal="100.00", grand_total="100.00")
        r = self.client.get(reverse("receipt", args=[txn.pk]))
        self.assertEqual(r.status_code, 200)


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
        self.assertContains(r, "protected")
        self.assertContains(r, "1")  # protected_count


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
        self.cat = Category.objects.create(name="Test")
        self.item = Item.objects.create(
            category=self.cat, name="Void Item", sku="V-001",
            emoji="💔", cost_price=10, selling_price=50, stock_qty=10
        )
        self.txn = Transaction.objects.create(
            subtotal="100.00", grand_total="100.00", status="COMPLETED"
        )
        TransactionItem.objects.create(
            transaction=self.txn, item=self.item, quantity=2,
            unit_price=50, total_price=100
        )

    def test_void_restores_stock(self):
        r = self.client.post(reverse("transaction_void", args=[self.txn.pk]))
        self.assertRedirects(r, reverse("sales_history"))
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, "VOIDED")
        self.assertEqual(self.txn.grand_total, 0)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_qty, 12)  # restored 2 units


# ===================== STOCK ADJUST TEST =====================

class StockAdjustTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.cat = Category.objects.create(name="Test")
        self.item = Item.objects.create(
            category=self.cat, name="Stock Adjust", sku="STK-001",
            emoji="📦", cost_price=10, selling_price=20, stock_qty=5
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
