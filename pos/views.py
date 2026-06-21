"""Views for Ipo-Ipo POS."""

import json
from decimal import Decimal
from django.db import models as dj_models
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from .models import Item, Category, Transaction, TransactionItem, DiscountType
from .services import CheckoutEngine


def home(request):
    """Main POS dashboard with product grid and cart."""
    search_q = request.GET.get("q", "")
    items_qs = Item.objects.filter(is_active=True).select_related("category").order_by("category__name", "name")
    if search_q:
        items_qs = items_qs.filter(name__icontains=search_q)
    items = items_qs
    discounts = DiscountType.objects.filter(is_active=True)

    # Dashboard stats
    completed_txns = Transaction.objects.filter(status="COMPLETED")
    today_sales_agg = completed_txns.aggregate(total=dj_models.Sum("grand_total"))
    today_sales = today_sales_agg["total"] or Decimal("0.00")
    active_orders = completed_txns.count()
    avg_ticket = (today_sales / Decimal(active_orders)).quantize(Decimal("0.01")) if active_orders > 0 else Decimal("0.00")
    low_stock_count = Item.objects.filter(is_active=True, stock_qty__lte=dj_models.F("low_stock_threshold")).count()

    context = {
        "nav_active": "dashboard",
        "items": items,
        "discounts": discounts,
        "today_sales": today_sales,
        "avg_ticket": avg_ticket,
        "active_orders": active_orders,
        "low_stock_count": low_stock_count,
    }
    return render(request, "pos/home.html", context)


class InventoryDashboardView(ListView):
    model = Item
    template_name = "inventory/dashboard.html"
    context_object_name = "inventory_items"

    def get_queryset(self):
        return Item.objects.filter(is_active=True).select_related("category").order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "inventory"
        return ctx


class ItemCreateView(CreateView):
    model = Item
    fields = [
        "category", "name", "sku", "emoji", "image",
        "cost_price", "selling_price", "stock_qty", "low_stock_threshold",
    ]
    template_name = "inventory/item_form.html"
    success_url = reverse_lazy("inventory_dashboard")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "inventory"
        return ctx


class ItemUpdateView(UpdateView):
    model = Item
    fields = [
        "category", "name", "sku", "emoji", "image",
        "cost_price", "selling_price", "stock_qty", "low_stock_threshold", "is_active",
    ]
    template_name = "inventory/item_form.html"
    success_url = reverse_lazy("inventory_dashboard")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "inventory"
        return ctx


def sales_history(request):
    """List of completed transactions only."""
    transactions = Transaction.objects.filter(status="COMPLETED").order_by("-timestamp")[:100]
    return render(request, "pos/sales.html", {
        "nav_active": "sales",
        "transactions": transactions,
    })


def reports(request):
    """Simple reports dashboard."""
    total_sales = sum(t.grand_total for t in Transaction.objects.all())
    total_transactions = Transaction.objects.count()
    avg_per_txn = total_sales / total_transactions if total_transactions > 0 else 0
    top_items = (
        TransactionItem.objects.values("item__name", "item__emoji")
        .annotate(total_qty=dj_models.Sum("quantity"))
        .order_by("-total_qty")[:10]
    )
    return render(request, "pos/reports.html", {
        "nav_active": "reports",
        "total_sales": total_sales,
        "total_transactions": total_transactions,
        "avg_per_txn": avg_per_txn,
        "top_items": top_items,
    })


def customers(request):
    """Customers page (placeholder — no login/auth)."""
    return render(request, "pos/customers.html", {
        "nav_active": "customers",
    })


def product_catalog(request):
    """Full product catalog view."""
    items = Item.objects.filter(is_active=True).select_related("category").order_by("category__name", "name")
    return render(request, "pos/products.html", {
        "nav_active": "products",
        "items": items,
    })


@csrf_exempt
def checkout_submit_api(request):
    """JSON API for processing a POS checkout."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid method"}, status=405)

    try:
        payload = json.loads(request.body)
        raw_cart = payload.get("cart", [])
        discount_id = payload.get("discount_id", None)
        pay_method = payload.get("payment_method", "CASH")
        ref_num = payload.get("reference_number", None)
        diners = int(payload.get("total_diners", 1))
        specials = int(payload.get("special_count", 0))

        # Normalize: frontend sends 'quantity', engine reads 'qty'
        cart = []
        for entry in raw_cart:
            qty = entry.get("quantity") or entry.get("qty")
            cart.append({"item_id": entry["item_id"], "qty": qty})

        if not cart:
            return JsonResponse({"status": "error", "message": "Cart empty"}, status=400)

        engine = CheckoutEngine(
            cart_data=cart,
            discount_id=discount_id,
            payment_method=pay_method,
            ref_num=ref_num,
            total_diners=diners,
            special_count=specials,
        )

        executed_txn = engine.process()
        return JsonResponse({
            "status": "success",
            "transaction_id": executed_txn.id,
            "grand_total": str(executed_txn.grand_total),
        })

    except ValueError as val_err:
        return JsonResponse({"status": "error", "message": str(val_err)}, status=400)
    except ValueError as val_err:
        return JsonResponse({"status": "error", "message": str(val_err)}, status=400)
    except Exception:
        return JsonResponse({"status": "error", "message": "Processing fault"}, status=500)


def receipt(request, pk):
    """Receipt view for a completed transaction."""
    txn = get_object_or_404(Transaction.objects.prefetch_related("line_items__item"), pk=pk)
    return render(request, "pos/receipt.html", {
        "transaction": txn,
    })


# ===================== CATEGORY CRUD =====================

class CategoryListView(ListView):
    model = Category
    template_name = "inventory/category_list.html"
    context_object_name = "categories"
    ordering = ["name"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "categories"
        return ctx


class CategoryCreateView(CreateView):
    model = Category
    fields = ["name", "description"]
    template_name = "inventory/category_form.html"
    success_url = reverse_lazy("category_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "categories"
        return ctx


class CategoryUpdateView(UpdateView):
    model = Category
    fields = ["name", "description"]
    template_name = "inventory/category_form.html"
    success_url = reverse_lazy("category_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "categories"
        return ctx


class CategoryDeleteView(DeleteView):
    model = Category
    template_name = "inventory/category_confirm_delete.html"
    success_url = reverse_lazy("category_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "categories"
        if "protected" in kwargs:
            ctx["protected"] = kwargs["protected"]
            ctx["protected_count"] = kwargs["protected_count"]
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            self.object.delete()
            return redirect(self.success_url)
        except dj_models.ProtectedError:
            count = self.object.items.count()
            return self.render_to_response(
                self.get_context_data(protected=True, protected_count=count)
            )



# ===================== DISCOUNTTYPE CRUD =====================

class DiscountTypeListView(ListView):
    model = DiscountType
    template_name = "pos/discount_list.html"
    context_object_name = "discounts"
    ordering = ["name"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "discounts"
        return ctx


class DiscountTypeCreateView(CreateView):
    model = DiscountType
    fields = ["name", "kind", "value", "is_active"]
    template_name = "pos/discount_form.html"
    success_url = reverse_lazy("discount_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "discounts"
        return ctx


class DiscountTypeUpdateView(UpdateView):
    model = DiscountType
    fields = ["name", "kind", "value", "is_active"]
    template_name = "pos/discount_form.html"
    success_url = reverse_lazy("discount_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "discounts"
        return ctx


class DiscountTypeDeleteView(DeleteView):
    model = DiscountType
    template_name = "pos/discount_confirm_delete.html"
    success_url = reverse_lazy("discount_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "discounts"
        return ctx


# ===================== ITEM DELETE =====================

class ItemDeleteView(DeleteView):
    model = Item
    template_name = "inventory/item_confirm_delete.html"
    success_url = reverse_lazy("inventory_dashboard")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "inventory"
        return ctx


# ===================== STOCK ADJUST =====================

class InventoryStockAdjustView(View):
    def post(self, request, pk):
        item = get_object_or_404(Item, pk=pk)
        new_qty = request.POST.get("stock_qty")
        if new_qty is not None:
            try:
                item.stock_qty = int(new_qty)
                item.save()
            except (ValueError, TypeError):
                pass
        return redirect("inventory_dashboard")


# ===================== TRANSACTION VOID =====================

class TransactionVoidView(View):
    def post(self, request, pk):
        txn = get_object_or_404(Transaction.objects.prefetch_related("line_items__item"), pk=pk)

        if txn.status != "COMPLETED":
            return redirect("sales_history")

        for line in txn.line_items.all():
            line.item.stock_qty += line.quantity
            line.item.save()

        txn.status = "VOIDED"
        txn.grand_total = Decimal("0.00")
        txn.discount_amount = Decimal("0.00")
        txn.save()

        return redirect("sales_history")
