from django.db import models
from decimal import Decimal


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Item(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="items")
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
    stock_qty = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)

    def display_icon(self):
        """Returns emoji if set, otherwise a generic fallback."""
        return self.emoji or "📦"

    def __str__(self):
        return f"{self.display_icon()} {self.name} ({self.sku})"


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
    total_diners = models.PositiveIntegerField(default=1)
    special_cardholders_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"TXN-{self.id} | {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


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
