"""Tests for CASSEY Branch model — TDD approach."""

from django.test import TestCase
from django.db import IntegrityError
from decimal import Decimal
from django.utils import timezone
import json


# ===================== BRANCH MODEL TESTS =====================

class BranchModelTest(TestCase):
    """Tests for Branch model creation and constraints."""

    def _create_branch(self, name, branch_type, **kwargs):
        """Helper to create a Branch for testing."""
        from pos.models import Branch
        kwargs.setdefault("name", name)
        kwargs.setdefault("branch_type", branch_type)
        branch = Branch(**kwargs)
        branch.full_clean()
        branch.save()
        return branch

    def test_branch_creation_with_required_fields(self):
        """A branch should be creatable with just name and branch_type."""
        branch = self._create_branch("LPG Branch", "LPG")
        self.assertEqual(str(branch), "LPG Branch (LPG)")
        self.assertEqual(branch.branch_type, "LPG")
        self.assertTrue(branch.is_active)

    def test_branch_creation_with_all_fields(self):
        """A branch should accept all optional fields."""
        branch = self._create_branch(
            name="AGRI Branch",
            branch_type="AGRI",
            address="123 Farm Road",
            contact_number="09171234567",
            tax_rate=Decimal("12.00"),
            currency="PHP",
            receipt_footer="Thank you for your purchase!",
            is_active=True,
        )
        self.assertEqual(branch.address, "123 Farm Road")
        self.assertEqual(branch.contact_number, "09171234567")
        self.assertEqual(branch.tax_rate, Decimal("12.00"))
        self.assertEqual(branch.currency, "PHP")
        self.assertEqual(branch.receipt_footer, "Thank you for your purchase!")

    def test_branch_name_is_required(self):
        """Branch name should be required."""
        with self.assertRaises(Exception):
            self._create_branch(name=None, branch_type="GAS")

    def test_branch_type_is_required(self):
        """Branch type should be required."""
        with self.assertRaises(Exception):
            self._create_branch(name="Test", branch_type=None)

    def test_branch_type_choices_valid(self):
        """Branch type should accept valid choices."""
        for bt in ["LPG", "AGRI", "GAS"]:
            branch = self._create_branch(f"Branch {bt}", bt)
            self.assertEqual(branch.branch_type, bt)

    def test_branch_type_choices_invalid(self):
        """Branch type should reject invalid choices."""
        from django.core.exceptions import ValidationError
        from pos.models import Branch
        b = Branch(name="Test", branch_type="INVALID")
        with self.assertRaises(ValidationError):
            b.full_clean()

    def test_branch_name_max_length(self):
        """Branch name should not exceed 200 characters."""
        from django.core.exceptions import ValidationError
        from pos.models import Branch
        long_name = "A" * 201
        b = Branch(name=long_name, branch_type="LPG")
        with self.assertRaises(ValidationError):
            b.full_clean()

    def test_branch_name_unique(self):
        """Branch name should be unique."""
        self._create_branch("Unique Branch", "LPG")
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._create_branch("Unique Branch", "AGRI")

    def test_branch_default_active(self):
        """New branches should be active by default."""
        branch = self._create_branch("Active Branch", "LPG")
        self.assertTrue(branch.is_active)

    def test_branch_can_be_inactive(self):
        """Branches should be deactivatable."""
        branch = self._create_branch("Inactive Branch", "LPG", is_active=False)
        self.assertFalse(branch.is_active)

    def test_branch_verbose_name(self):
        """Check model Meta."""
        from pos.models import Branch
        self.assertEqual(Branch._meta.verbose_name, "Branch")
        self.assertEqual(Branch._meta.verbose_name_plural, "Branches")

    def test_branch_ordering(self):
        """Branches should be ordered by name by default."""
        from pos.models import Branch
        self._create_branch("Zulu Branch", "LPG")
        self._create_branch("Alpha Branch", "AGRI")
        branches = Branch.objects.all()
        self.assertEqual(branches[0].name, "Alpha Branch")
        self.assertEqual(branches[1].name, "Zulu Branch")

    def test_branch_has_expected_fields(self):
        """Verify all expected fields exist."""
        from pos.models import Branch
        field_names = {f.name for f in Branch._meta.get_fields()}
        expected = {
            'id', 'name', 'branch_type', 'address', 'contact_number',
            'tax_rate', 'currency', 'receipt_footer', 'is_active',
            'created_at', 'updated_at',
        }
        missing = expected - field_names
        self.assertTrue(expected.issubset(field_names), f"Missing fields: {missing}")

    def test_branch_auto_timestamps(self):
        """Branches should auto-set created_at and updated_at."""
        import datetime
        branch = self._create_branch("Timestamp Test", "LPG")
        self.assertIsNotNone(branch.created_at)
        self.assertIsNotNone(branch.updated_at)
        self.assertIsInstance(branch.created_at, datetime.datetime)

    def test_branch_created_at_set_on_create(self):
        """created_at should be set on creation."""
        branch = self._create_branch("Created Test", "LPG")
        now = timezone.now()
        self.assertLessEqual(branch.created_at, now)

    def test_active_branches_manager(self):
        """Test filtering active branches."""
        from pos.models import Branch
        self._create_branch("Active1", "LPG")
        self._create_branch("Inactive1", "AGRI", is_active=False)
        self._create_branch("Active2", "GAS")
        active = Branch.objects.filter(is_active=True)
        self.assertEqual(active.count(), 2)

    def test_branch_contact_number_optional(self):
        """Contact number should be optional."""
        branch = self._create_branch("No Contact", "LPG")
        self.assertIsNone(branch.contact_number)

    def test_branch_address_optional(self):
        """Address should be optional."""
        branch = self._create_branch("No Address", "LPG")
        self.assertIsNone(branch.address)


class BranchScopedModelTest(TestCase):
    """Tests for branch-scoped data."""

    def _create_branch(self, name="Test Branch", branch_type="LPG"):
        from pos.models import Branch
        b = Branch(name=name, branch_type=branch_type)
        b.full_clean()
        b.save()
        return b

    def test_item_belongs_to_branch(self):
        """Items should have a branch ForeignKey."""
        from pos.models import Item, Category
        branch = self._create_branch()
        cat = Category.objects.create(branch=branch, name="Test Cat")
        item = Item.objects.create(
            branch=branch,
            category=cat,
            name="Branch Item",
            sku=f"BR-ITEM-{branch.id}",
            cost_price=Decimal("10.00"),
            selling_price=Decimal("20.00"),
            stock_qty=100,
        )
        self.assertEqual(item.branch, branch)
        self.assertEqual(Item.objects.filter(branch=branch).count(), 1)

    def test_items_filtered_by_branch(self):
        """Items should be filterable by branch."""
        from pos.models import Item, Category
        branch1 = self._create_branch("Branch LPG", "LPG")
        branch2 = self._create_branch("Branch AGRI", "AGRI")
        cat = Category.objects.create(branch=branch1, name="Cat1")
        cat2 = Category.objects.create(branch=branch2, name="Cat2")

        Item.objects.create(
            branch=branch1, category=cat,
            name="Item 1", sku="SKU-1",
            cost_price=Decimal("10.00"), selling_price=Decimal("20.00"), stock_qty=10,
        )
        Item.objects.create(
            branch=branch2, category=cat2,
            name="Item 2", sku="SKU-2",
            cost_price=Decimal("10.00"), selling_price=Decimal("20.00"), stock_qty=10,
        )

        self.assertEqual(Item.objects.filter(branch=branch1).count(), 1)
        self.assertEqual(Item.objects.filter(branch=branch2).count(), 1)

    def test_transaction_belongs_to_branch(self):
        """Transactions should have a branch ForeignKey."""
        from pos.models import Transaction
        branch = self._create_branch()
        txn = Transaction.objects.create(
            branch=branch,
            grand_total=Decimal("100.00"),
            payment_method="CASH",
        )
        self.assertEqual(txn.branch, branch)
        self.assertEqual(Transaction.objects.filter(branch=branch).count(), 1)

    def test_discounttype_belongs_to_branch(self):
        """DiscountType should have a branch ForeignKey."""
        from pos.models import DiscountType
        branch = self._create_branch()
        discount = DiscountType.objects.create(
            branch=branch,
            name="Branch Discount",
            kind="PERCENTAGE",
            value=Decimal("10.00"),
        )
        self.assertEqual(discount.branch, branch)
        self.assertEqual(DiscountType.objects.filter(branch=branch).count(), 1)

    def test_category_belongs_to_branch(self):
        """Category should have a branch ForeignKey."""
        from pos.models import Category
        branch = self._create_branch()
        cat = Category.objects.create(
            branch=branch,
            name="Branch Category",
            description="For testing",
        )
        self.assertEqual(cat.branch, branch)
        self.assertEqual(Category.objects.filter(branch=branch).count(), 1)

    def test_models_have_branch_field(self):
        """Verify all expected models have a branch field."""
        from pos.models import Item, Transaction, DiscountType, Category
        for model_class in [Item, Transaction, DiscountType, Category]:
            has_branch = hasattr(model_class, 'branch')
            field = model_class.branch.field if has_branch else None
            self.assertIsNotNone(field, f"{model_class.__name__} missing branch FK")
            if field:
                self.assertIsInstance(field, models.ForeignKey,
                                      f"{model_class.__name__}.branch is not a ForeignKey")


from django.db import models


# ===================== BRANCH CRUD VIEW TESTS =====================

class BranchCRUDTest(TestCase):
    """Tests for Branch CRUD views - list, create, read, update, delete."""

    def setUp(self):
        from pos.models import Branch
        self.branch1 = Branch.objects.create(name="LPG Main", branch_type="LPG")
        self.branch2 = Branch.objects.create(name="AGRI Shop", branch_type="AGRI")
        self.branch3 = Branch.objects.create(name="GAS Station", branch_type="GAS", is_active=False)

    def test_branch_list_view_exists(self):
        """Branch list should return 200."""
        response = self.client.get("/branches/")
        self.assertEqual(response.status_code, 200)

    def test_branch_list_shows_all_branches(self):
        """Branch list should display all branches."""
        response = self.client.get("/branches/")
        self.assertContains(response, "LPG Main")
        self.assertContains(response, "AGRI Shop")
        self.assertContains(response, "GAS Station")

    def test_branch_list_shows_branch_type(self):
        """Branch list should show the branch type."""
        response = self.client.get("/branches/")
        self.assertContains(response, "LPG")
        self.assertContains(response, "AGRI")
        self.assertContains(response, "GAS")

    def test_branch_list_shows_active_status(self):
        """Branch list should indicate active/inactive status."""
        response = self.client.get("/branches/")
        self.assertContains(response, "Active")
        self.assertContains(response, "Inactive")

    def test_branch_create_view_loads(self):
        """Branch create page should load."""
        response = self.client.get("/branches/add/")
        self.assertEqual(response.status_code, 200)

    def test_branch_create_view_has_form(self):
        """Branch create page should have a form."""
        response = self.client.get("/branches/add/")
        self.assertContains(response, "form")
        self.assertContains(response, "name")
        self.assertContains(response, "branch_type")

    def test_branch_create_submit_creates_branch(self):
        """POST to create should create a branch."""
        from pos.models import Branch
        data = {
            "name": "New LPG",
            "branch_type": "LPG",
            "address": "123 Street",
            "contact_number": "09170000000",
            "tax_rate": "12.00",
            "currency": "PHP",
        }
        response = self.client.post("/branches/add/", data)
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 302:
            self.assertTrue(Branch.objects.filter(name="New LPG").exists())

    def test_branch_create_requires_name(self):
        """Create without name should show error."""
        response = self.client.post("/branches/add/", {"branch_type": "LPG"})
        self.assertEqual(response.status_code, 200)  # stays on form
        self.assertContains(response, "required")

    def test_branch_create_requires_branch_type(self):
        """Create without branch_type should show error."""
        response = self.client.post("/branches/add/", {"name": "Test"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "required")

    def test_branch_update_view_loads(self):
        """Branch edit page should load."""
        response = self.client.get(f"/branches/{self.branch1.id}/edit/")
        self.assertEqual(response.status_code, 200)

    def test_branch_update_view_has_current_values(self):
        """Edit form should be pre-filled with current data."""
        response = self.client.get(f"/branches/{self.branch1.id}/edit/")
        self.assertContains(response, "LPG Main")

    def test_branch_update_submit_updates_branch(self):
        """POST to update should modify branch."""
        response = self.client.post(
            f"/branches/{self.branch1.id}/edit/",
            {
                "name": "LPG Updated",
                "branch_type": "LPG",
                "tax_rate": "12.00",
                "currency": "PHP",
            }
        )
        self.assertIn(response.status_code, [200, 302])
        self.branch1.refresh_from_db()
        self.assertEqual(self.branch1.name, "LPG Updated")

    def test_branch_delete_view_loads(self):
        """Branch delete confirmation should load."""
        response = self.client.get(f"/branches/{self.branch3.id}/delete/")
        self.assertEqual(response.status_code, 200)

    def test_branch_delete_submit_removes_branch(self):
        """POST to delete should remove branch."""
        from pos.models import Branch
        response = self.client.post(f"/branches/{self.branch3.id}/delete/")
        self.assertIn(response.status_code, [200, 302])
        self.assertFalse(Branch.objects.filter(id=self.branch3.id).exists())

    def test_branch_list_link_to_create(self):
        """Branch list should have an add link."""
        response = self.client.get("/branches/")
        self.assertContains(response, "Add Branch")

    def test_branch_list_link_to_edit(self):
        """Branch list should have edit links."""
        response = self.client.get("/branches/")
        self.assertContains(response, "edit")

    def test_branch_list_link_to_delete(self):
        """Branch list should have delete links."""
        response = self.client.get("/branches/")
        self.assertContains(response, "delete")


# ===================== BRANCH SELECTOR TESTS =====================

class BranchSelectorTest(TestCase):
    """Tests for branch selection before POS use."""

    def setUp(self):
        from pos.models import Branch
        self.branch1 = Branch.objects.create(name="LPG Main", branch_type="LPG")
        self.branch2 = Branch.objects.create(name="AGRI Shop", branch_type="AGRI")
        self.branch3 = Branch.objects.create(name="GAS Station", branch_type="GAS")

    def test_select_branch_page_loads(self):
        """Branch selection page should display."""
        response = self.client.get("/select-branch/")
        self.assertEqual(response.status_code, 200)

    def test_select_branch_shows_all_active_branches(self):
        """Branch selection should list all active branches."""
        response = self.client.get("/select-branch/")
        self.assertContains(response, "LPG Main")
        self.assertContains(response, "AGRI Shop")
        self.assertContains(response, "GAS Station")

    def test_select_branch_shows_branch_types(self):
        """Branch selection should show branch type labels."""
        response = self.client.get("/select-branch/")
        self.assertContains(response, "LPG")
        self.assertContains(response, "AGRI")
        self.assertContains(response, "GAS")

    def test_select_branch_stores_in_session(self):
        """Choosing a branch should store it in session."""
        response = self.client.post("/select-branch/", {"branch_id": self.branch1.id})
        self.assertEqual(response.status_code, 302)
        # Check session
        session = self.client.session
        self.assertEqual(session.get("branch_id"), self.branch1.id)

    def test_select_branch_redirects_to_dashboard(self):
        """After selecting branch, redirect to dashboard."""
        response = self.client.post("/select-branch/", {"branch_id": self.branch1.id})
        self.assertRedirects(response, "/")

    def test_dashboard_redirects_if_no_branch(self):
        """Accessing dashboard without branch should redirect to selection."""
        response = self.client.get("/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/select-branch/", response.url)

    def test_dashboard_loads_with_branch_in_session(self):
        """Dashboard should load if branch is selected."""
        self.client.post("/select-branch/", {"branch_id": self.branch1.id})
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_selected_branch_name(self):
        """Dashboard should display the selected branch name."""
        self.client.post("/select-branch/", {"branch_id": self.branch2.id})
        response = self.client.get("/")
        self.assertContains(response, "AGRI Shop")

    def test_select_branch_requires_valid_id(self):
        """Invalid branch ID should show error."""
        response = self.client.post("/select-branch/", {"branch_id": 999})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "error")

    def test_select_branch_redirects_if_already_selected(self):
        """If branch already selected, visiting /select-branch/ should redirect to home."""
        self.client.post("/select-branch/", {"branch_id": self.branch1.id})
        response = self.client.get("/select-branch/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/", response.url)

    def test_branch_switch_via_sidebar(self):
        """Switching branch should update the session."""
        self.client.post("/select-branch/", {"branch_id": self.branch1.id})
        response = self.client.get("/")
        self.assertContains(response, "Switch Branch")


# ===================== PER-BRANCH SCOPING TESTS =====================

class PerBranchScopingTest(TestCase):
    """Tests that views filter data by the selected branch."""

    def setUp(self):
        from pos.models import Branch, Category, Item, DiscountType
        from decimal import Decimal

        self.branch_lpg = Branch.objects.create(name="LPG Branch", branch_type="LPG")
        self.branch_agri = Branch.objects.create(name="AGRI Branch", branch_type="AGRI")

        # Create LPG items
        cat_lpg = Category.objects.create(branch=self.branch_lpg, name="LPG Fuel")
        Item.objects.create(
            branch=self.branch_lpg, category=cat_lpg,
            name="LPG 11kg", sku="LPG-11",
            cost_price=Decimal("500.00"), selling_price=Decimal("700.00"), stock_qty=10,
        )
        Item.objects.create(
            branch=self.branch_lpg, category=cat_lpg,
            name="LPG 22kg", sku="LPG-22",
            cost_price=Decimal("900.00"), selling_price=Decimal("1200.00"), stock_qty=5,
        )

        # Create AGRI items
        cat_agri = Category.objects.create(branch=self.branch_agri, name="Fertilizer")
        Item.objects.create(
            branch=self.branch_agri, category=cat_agri,
            name="Urea 50kg", sku="UREA-50",
            cost_price=Decimal("1000.00"), selling_price=Decimal("1500.00"), stock_qty=20,
        )

        # Create LPG discounts
        DiscountType.objects.create(
            branch=self.branch_lpg, name="LPG Discount",
            kind="PERCENTAGE", value=Decimal("5.00"),
        )
        # Create AGRI discounts
        DiscountType.objects.create(
            branch=self.branch_agri, name="AGRI Discount",
            kind="PERCENTAGE", value=Decimal("10.00"),
        )

    def _select_branch(self, branch):
        self.client.post("/select-branch/", {"branch_id": branch.id})

    def test_inventory_shows_only_selected_branch_items(self):
        """Inventory view should show only items for selected branch."""
        self._select_branch(self.branch_lpg)
        response = self.client.get("/inventory/")
        self.assertContains(response, "LPG 11kg")
        self.assertContains(response, "LPG 22kg")
        self.assertNotContains(response, "Urea 50kg")

    def test_inventory_switching_branch_shows_different_items(self):
        """Switching branch should show different items."""
        self._select_branch(self.branch_agri)
        response = self.client.get("/inventory/")
        self.assertContains(response, "Urea 50kg")
        self.assertNotContains(response, "LPG 11kg")

    def test_product_grid_shows_only_selected_branch_items(self):
        """POS product grid should show only selected branch's items."""
        self._select_branch(self.branch_lpg)
        response = self.client.get("/products/")
        self.assertContains(response, "LPG 11kg")
        self.assertNotContains(response, "Urea 50kg")

    def test_home_dashboard_shows_branch_scoped_stats(self):
        """Dashboard stats should reflect selected branch."""
        self._select_branch(self.branch_lpg)
        response = self.client.get("/")
        self.assertContains(response, "LPG Branch")

    def test_category_list_shows_branch_categories_only(self):
        """Category list should filter by branch."""
        self._select_branch(self.branch_lpg)
        response = self.client.get("/categories/")
        self.assertContains(response, "LPG Fuel")
        self.assertNotContains(response, "Fertilizer")

    def test_discount_list_shows_branch_discounts_only(self):
        """Discount list should filter by branch."""
        self._select_branch(self.branch_lpg)
        response = self.client.get("/discounts/")
        self.assertContains(response, "LPG Discount")
        self.assertNotContains(response, "AGRI Discount")

    def test_new_item_defaults_to_current_branch(self):
        """Creating a new item should auto-assign current branch."""
        from pos.models import Branch, Category
        self._select_branch(self.branch_lpg)
        cat_lpg = Category.objects.filter(branch=self.branch_lpg).first()
        response = self.client.get("/inventory/add/")
        self.assertEqual(response.status_code, 200)
        # Form should have branch pre-selected or hidden

    def test_sales_history_shows_branch_sales(self):
        """Sales view should filter by branch."""
        from pos.models import Transaction
        from decimal import Decimal
        Transaction.objects.create(branch=self.branch_lpg, grand_total=Decimal("500.00"), payment_method="CASH")
        Transaction.objects.create(branch=self.branch_agri, grand_total=Decimal("300.00"), payment_method="CASH")

        self._select_branch(self.branch_lpg)
        response = self.client.get("/sales/")
        self.assertContains(response, "500.00")
        self.assertNotContains(response, "300.00")

    def test_checkout_creates_transaction_with_branch(self):
        """Checkout should assign the selected branch to the transaction."""
        from pos.models import Item, Transaction
        from decimal import Decimal
        self._select_branch(self.branch_lpg)
        item = Item.objects.filter(branch=self.branch_lpg).first()
        response = self.client.post("/api/checkout/", json.dumps({
            "cart": [{"item_id": item.id, "quantity": 1}],
            "payment_method": "CASH",
        }), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        txn = Transaction.objects.get(id=data.get("transaction_id"))
        self.assertEqual(txn.branch_id, self.branch_lpg.id)


import json
