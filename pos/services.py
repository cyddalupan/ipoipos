"""Business logic for Ipo-Ipo POS."""

from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction as db_transaction
from .models import Item, Transaction, TransactionItem, DiscountType


class CheckoutEngine:
    """Processes a POS checkout cart with optional discounts."""

    def __init__(self, cart_data, discount_id=None, payment_method="CASH",
                 ref_num=None, total_diners=1, special_count=0):
        self.cart_data = cart_data
        self.discount_id = discount_id
        self.payment_method = payment_method
        self.ref_num = ref_num
        self.total_diners = total_diners
        self.special_count = special_count

        self.subtotal = Decimal("0.00")
        self.discount_amount = Decimal("0.00")
        self.vat_exempt_sales = Decimal("0.00")
        self.vat_amount = Decimal("0.00")
        self.grand_total = Decimal("0.00")

    def calculate_totals(self, discount_obj):
        for entry in self.cart_data:
            item = Item.objects.get(id=entry["item_id"])
            self.subtotal += item.selling_price * Decimal(entry["qty"])

        if discount_obj and discount_obj.is_active:
            if discount_obj.kind == "PERCENTAGE":
                self.discount_amount = (self.subtotal * (discount_obj.value / Decimal("100.00"))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                vtable_balance = self.subtotal - self.discount_amount
                self.vat_exclusive_sales = (vtable_balance / Decimal("1.12")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                self.vat_amount = vtable_balance - self.vat_exclusive_sales
                self.grand_total = vtable_balance

            elif discount_obj.kind == "FIXED":
                self.discount_amount = discount_obj.value
                vtable_balance = max(Decimal("0.00"), self.subtotal - self.discount_amount)
                self.vat_exclusive_sales = (vtable_balance / Decimal("1.12")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                self.vat_amount = vtable_balance - self.vat_exclusive_sales
                self.grand_total = vtable_balance

            elif discount_obj.kind == "PH_SPECIAL":
                gross_share = (self.subtotal / Decimal(self.total_diners)) * Decimal(self.special_count)
                vat_component_in_share = (gross_share - (gross_share / Decimal("1.12"))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                exempt_base = (gross_share / Decimal("1.12")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                law_discount = (exempt_base * Decimal("0.20")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)

                self.discount_amount = law_discount
                self.grand_total = (self.subtotal - vat_component_in_share - law_discount).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                self.vat_exclusive_sales = (self.grand_total / Decimal("1.12")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                self.vat_amount = self.grand_total - self.vat_exclusive_sales
        else:
            self.vat_exclusive_sales = (self.subtotal / Decimal("1.12")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP)
            self.vat_amount = self.subtotal - self.vat_exclusive_sales
            self.grand_total = self.subtotal

    def process(self):
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
                item = Item.objects.select_for_update().get(id=entry["item_id"])
                if item.stock_qty < entry["qty"]:
                    raise ValueError(f"Insufficient stock for product: {item.name}")

                TransactionItem.objects.create(
                    transaction=txn,
                    item=item,
                    quantity=entry["qty"],
                    unit_price=item.selling_price,
                )
                item.stock_qty -= entry["qty"]
                item.save()

            return txn
