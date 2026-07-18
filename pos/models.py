from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Branch(models.Model):
    class Type(models.TextChoices):
        LPG = "LPG", "LPG Refilling Station"
        AGRI = "AGRI", "Agricultural Supply"
        GAS = "GAS", "Gas Station"
        RETAIL = "RETAIL", "Retail Store"
        WHOLESALE = "WHOLESALE", "Wholesale"
        SERVICE = "SERVICE", "Service Business"
        MANUFACTURING = "MANUFACTURING", "Manufacturing"
        FOOD = "FOOD", "Food & Restaurant"
        HEALTH = "HEALTH", "Health & Pharmacy"
        EDUCATION = "EDUCATION", "Education"
        TRANSPORT = "TRANSPORT", "Transport & Logistics"
        CONSTRUCTION = "CONSTRUCTION", "Construction"
        TECH = "TECH", "Technology"
        OTHER = "OTHER", "Other"

    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=20, choices=Type.choices)
    code = models.CharField(max_length=20, unique=True, help_text="Short branch code (e.g., LPG-01, AGRI-01)")
    is_active = models.BooleanField(default=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12.00, help_text="Default tax rate %")
    currency = models.CharField(max_length=10, default="PHP")
    address = models.TextField(blank=True, null=True)
    contact = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "branches"

    def __str__(self):
        return f"[{self.get_type_display()}] {self.name}"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class MealSubcategory(models.Model):
    """
    Food group / meal subcategory for grouping food items.
    Examples: Chicken, Pork, Beef, Vegetables, Rice, Drinks
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    emoji = models.CharField(
        max_length=10, blank=True, default="",
        help_text="Emoji for visual display (e.g., 🍗🍚🥤)"
    )

    class Meta:
        verbose_name_plural = "meal subcategories"

    def __str__(self):
        return f"{self.emoji} {self.name}"


class Item(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="items")
    meal_subcategory = models.ForeignKey(
        MealSubcategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="items",
        help_text="Food group/meal subcategory for POS product filtering"
    )
    name = models.CharField(max_length=150, unique=True)
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU/Barcode")
    emoji = models.CharField(
        max_length=10, blank=True, null=True,
        help_text="Emoji for visual display (e.g., 🍗🍚🥤)"
    )
    image = models.ImageField(
        upload_to="product_images/", blank=True, null=True,
        help_text="Product image (optional, emoji used as fallback)"
    )
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True, help_text="Product description / details")
    stock_qty = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="items"
    )

    def display_icon(self):
        """Returns emoji if set, otherwise a generic fallback."""
        return self.emoji or "📦"

    def __str__(self):
        return f"{self.display_icon()} {self.name} ({self.sku})"


class ItemSize(models.Model):
    """Size variant for an item with per-size pricing.

    Examples: 11kg, 22kg, 50kg for LPG;
    Small, Medium, Large for retail;
    1L, 5L for gas/liquids.
    """
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="sizes"
    )
    name = models.CharField(
        max_length=100,
        help_text="Size label (e.g., 11kg, Small, 1L, XL)"
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Selling price for this size"
    )
    retail_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        blank=True, null=True,
        help_text="Retail price (falls back to price if not set)"
    )

    class Meta:
        unique_together = ["item", "name"]
        verbose_name_plural = "item sizes"
        ordering = ["item", "name"]

    def get_retail_price(self):
        return self.retail_price or self.price

    def __str__(self):
        return f"{self.item.name} — {self.name} (₱{self.price})"


class DiscountType(models.Model):
    DISCOUNT_CHOICES = [
        ("PERCENTAGE", "Percentage Based"),
        ("FIXED", "Fixed Cash Value"),
        ("PH_SPECIAL", "Philippine Statutory (Senior/PWD)"),
    ]
    name = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=20, choices=DISCOUNT_CHOICES, default="PERCENTAGE")
    value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Percentage value or exact cash deduction amount."
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.get_kind_display()}"


class Transaction(models.Model):
    PAYMENT_METHODS = [
        ("CASH", "Cash"),
        ("DIGITAL", "Digital Wallet (GCash/Maya)"),
    ]
    timestamp = models.DateTimeField(auto_now_add=True)
    branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transactions"
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_applied = models.ForeignKey(
        DiscountType, on_delete=models.PROTECT, null=True, blank=True
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    vat_exclusive_sales = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default="CASH")
    reference_number = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Trace ID for GCash/Maya validation"
    )
    status = models.CharField(
        max_length=10,
        choices=[("COMPLETED", "Completed"), ("VOIDED", "Voided")],
        default="COMPLETED"
    )
    void_reason = models.TextField(
        blank=True, null=True,
        help_text="Reason for voiding the transaction"
    )
    voided_at = models.DateTimeField(
        blank=True, null=True,
        help_text="When the transaction was voided"
    )
    ORDER_TYPES = [
        ("DINE_IN", "Dine-In"),
        ("TAKE_OUT", "Take-Out"),
    ]
    order_type = models.CharField(
        max_length=10, choices=ORDER_TYPES, default="DINE_IN",
        help_text="Order fulfillment type: DINE_IN or TAKE_OUT"
    )
    vat_inclusive = models.BooleanField(
        default=True,
        help_text="Whether 12% VAT is applied to this transaction"
    )
    total_diners = models.PositiveIntegerField(default=1)
    special_cardholders_count = models.PositiveIntegerField(default=0)
    table_number = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Dining table number (1-20), null for takeout"
    )
    shift = models.ForeignKey(
        'Shift', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transactions"
    )
    manual_discount_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Manual percentage discount (0-100%) applied to subtotal"
    )

    def __str__(self):
        return f"TXN-{self.id} | {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class Staff(models.Model):
    """Extends Django's auth User with role-based access for POS staff."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        CASHIER = "CASHIER", "Cashier"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff")
    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.CASHIER
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_members"
    )

    def save(self, *args, **kwargs):
        """Ensure user.is_staff is set for cashier accounts."""
        if not self.user.is_superuser:
            self.user.is_staff = True
            self.user.save(update_fields=["is_staff"])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} \u2014 {self.get_role_display()}"


class TransactionItem(models.Model):
    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="line_items"
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item.name} x{self.quantity} = ₱{self.total_price}"


class CashCount(models.Model):
    """Count of a single denomination during shift cash reconciliation."""

    shift = models.ForeignKey(
        'Shift', on_delete=models.CASCADE, related_name="cash_counts"
    )
    denomination_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Denomination value (e.g., 1000.00, 500.00, 100.00, 50.00, 20.00)"
    )
    quantity = models.PositiveIntegerField(default=0)
    subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        editable=False,
        help_text="Auto-computed: denomination_value * quantity"
    )

    def save(self, *args, **kwargs):
        self.subtotal = self.denomination_value * Decimal(self.quantity)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "cash counts"

    def __str__(self):
        return f"CashCount(Shift {self.shift.id}) ₱{self.denomination_value} x {self.quantity}"


class Shift(models.Model):
    """Tracks cashier work periods with starting/ending cash float."""

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"

    cashier = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="shifts"
    )
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    starting_float = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    ending_float = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="shifts"
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN
    )

    def __str__(self):
        return f"{self.cashier.username if self.cashier else 'System'} - {self.start_time} [{self.status}]"


class Expense(models.Model):
    """A cash expense recorded during a shift (e.g., supplies, delivery fees)."""

    shift = models.ForeignKey(
        Shift, on_delete=models.CASCADE, related_name="expenses"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"₱{self.amount} - {self.description} ({self.created_at.date()})"


class Patient(models.Model):
    """
    Patient record with FB Messenger PSID for chatbot integration
    and operational clinic remarks visible to LLM (not to patient verbatim).
    """

    name = models.CharField(max_length=255)
    fb_psid = models.CharField(
        max_length=255, unique=True,
        help_text="Facebook Messenger PSID for chatbot conversations"
    )
    remarks = models.TextField(
        null=True, blank=True,
        help_text="Operational clinic remarks visible to LLM but not revealed verbatim to patient"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.fb_psid})"


class Queue(models.Model):
    """
    Clinic queue entry linked to a Patient.
    Tracks the service a patient is receiving and its current status.
    Used by MessengerWebhookService to determine patient's queue state:
    - pre-registration: no Patient record linked to PSID
    - in-queue: at least one Queue entry with status='waiting'
    - post-queue: all Queue entries for the patient are served/cancelled/skipped
    """

    STATUS_CHOICES = [
        ("waiting", "Waiting"),
        ("served", "Served"),
        ("cancelled", "Cancelled"),
        ("skipped", "Skipped"),
    ]

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="queue_entries"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="waiting"
    )
    service = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Service requested (e.g., Check-up, Lab, X-Ray)"
    )
    service_area = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Clinic area/room where service is provided"
    )
    notes = models.TextField(
        blank=True, default="",
        help_text="Additional notes about the queue entry"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "queue entries"

    def __str__(self):
        return f"{self.patient.name} — {self.status} ({self.service or 'No service'})"

