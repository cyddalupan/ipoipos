"""Views for CASSEY POS."""

import json
from decimal import Decimal
from django.db import models as dj_models
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from .models import Item, ItemSize, Category, Transaction, TransactionItem, DiscountType, MealSubcategory, Shift, CashCount, Expense, Staff, Branch, Borrower
from .services import CheckoutEngine
from datetime import date



def _get_branch(request):
    """Get current branch from session. Returns None and clears session if invalid."""
    branch_id = request.session.get("current_branch_id")
    if branch_id:
        try:
            branch = Branch.objects.get(pk=branch_id, is_active=True)
            return branch
        except Branch.DoesNotExist:
            # Invalid branch in session — clear it so user sees branch_select
            request.session.pop("current_branch_id", None)
    return None


def branch_select(request):
    """Branch selector landing page before POS access."""
    branches = Branch.objects.filter(is_active=True)
    if request.method == "POST":
        branch_id = request.POST.get("branch_id")
        if branch_id:
            try:
                branch_id = int(branch_id)
                Branch.objects.get(pk=branch_id, is_active=True)
                request.session["current_branch_id"] = branch_id
                return redirect("home")
            except (ValueError, Branch.DoesNotExist):
                pass
    return render(request, "pos/branch_select.html", {
        "branches": branches,
    })


def branch_switch(request):
    """Switch branch and redirect back to previous page."""
    branch_id = request.GET.get("branch_id") or request.POST.get("branch_id")
    redirect_to = request.GET.get("next") or request.POST.get("next") or "home"
    if branch_id:
        request.session["current_branch_id"] = int(branch_id)
    return redirect(redirect_to)


def home(request):
    """Main POS dashboard with product grid and cart. Requires branch selection."""
    branch = _get_branch(request)
    if not branch:
        return redirect("branch_select")

    search_q = request.GET.get("q", "")
    items_qs = Item.objects.filter(is_active=True, branch=branch).select_related("category").prefetch_related("sizes").order_by("category__name", "name")
    if search_q:
        from django.db.models import Q
        items_qs = items_qs.filter(
            Q(name__icontains=search_q) | Q(sku__icontains=search_q)
        )
    items = items_qs
    discounts = DiscountType.objects.filter(is_active=True)
    categories = Category.objects.all().order_by("name")

    # Dashboard stats — scoped to branch
    completed_txns = Transaction.objects.filter(status="COMPLETED", branch=branch)
    today_sales_agg = completed_txns.aggregate(total=dj_models.Sum("grand_total"))
    today_sales = today_sales_agg["total"] or Decimal("0.00")
    active_orders = completed_txns.count()
    avg_ticket = (today_sales / Decimal(active_orders)).quantize(Decimal("0.01")) if active_orders > 0 else Decimal("0.00")
    low_stock_count = Item.objects.filter(is_active=True, stock_qty__lte=dj_models.F("low_stock_threshold"), branch=branch).count()

    context = {
        "nav_active": "dashboard",
        "items": items,
        "discounts": discounts,
        "categories": categories,
        "today_sales": today_sales,
        "avg_ticket": avg_ticket,
        "active_orders": active_orders,
        "low_stock_count": low_stock_count,
        "show_branch_switcher": True,
        "search_q": search_q,
    }
    return render(request, "pos/home.html", context)


def pos_order(request):
    """Dedicated POS order page — product grid, category filter, cart, and checkout."""
    branch = _get_branch(request)
    if not branch:
        return redirect("branch_select")

    search_q = request.GET.get("q", "")
    items_qs = Item.objects.filter(is_active=True, branch=branch).select_related("category").prefetch_related("sizes").order_by("category__name", "name")
    if search_q:
        from django.db.models import Q
        items_qs = items_qs.filter(
            Q(name__icontains=search_q) | Q(sku__icontains=search_q)
        )
    items = items_qs
    discounts = DiscountType.objects.filter(is_active=True)
    categories = Category.objects.all().order_by("name")

    context = {
        "nav_active": "pos_order",
        "items": items,
        "discounts": discounts,
        "categories": categories,
        "show_branch_switcher": True,
        "search_q": search_q,
    }
    return render(request, "pos/pos_order.html", context)


class InventoryDashboardView(ListView):
    model = Item
    template_name = "inventory/dashboard.html"
    context_object_name = "inventory_items"

    def dispatch(self, request, *args, **kwargs):
        branch = _get_branch(request)
        if not branch:
            return redirect("branch_select")
        self._branch = branch
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Item.objects.filter(is_active=True, branch=self._branch).select_related("category").prefetch_related("sizes").order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "inventory"
        ctx["categories"] = Category.objects.all().order_by("name")
        items = ctx.get("inventory_items", [])
        ctx["total_value"] = sum(
            (item.cost_price * item.stock_qty) for item in items
        )
        ctx["category_count"] = Category.objects.count()
        ctx["low_stock_count"] = sum(
            1 for item in items if item.stock_qty <= item.low_stock_threshold
        )
        ctx["low_stock_items"] = [
            item for item in items if item.stock_qty <= item.low_stock_threshold
        ]
        return ctx


class ItemCreateView(CreateView):
    model = Item
    fields = [
        "category", "name", "sku", "emoji", "image",
        "cost_price", "selling_price", "stock_qty", "low_stock_threshold",
        "description",
    ]
    template_name = "inventory/item_form.html"
    success_url = reverse_lazy("inventory_dashboard")

    def dispatch(self, request, *args, **kwargs):
        branch = _get_branch(request)
        if not branch:
            return redirect("branch_select")
        self._branch = branch
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.branch = self._branch
        response = super().form_valid(form)
        self._save_sizes(form.instance)
        return response

    def _save_sizes(self, item):
        """Save size data from POST."""
        size_names = self.request.POST.getlist("size_name[]")
        size_prices = self.request.POST.getlist("size_price[]")
        size_retails = self.request.POST.getlist("size_retail_price[]")
        # Clear existing sizes and recreate
        item.sizes.all().delete()
        for i, name in enumerate(size_names):
            name = name.strip()
            if not name:
                continue
            price = size_prices[i] if i < len(size_prices) else "0"
            retail = size_retails[i] if i < len(size_retails) else ""
            try:
                kwargs = {
                    "name": name,
                    "price": Decimal(price),
                }
                if retail:
                    kwargs["retail_price"] = Decimal(retail)
                ItemSize.objects.create(item=item, **kwargs)
            except (ValueError, TypeError):
                pass

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "inventory"
        ctx["categories"] = Category.objects.all().order_by("name")
        return ctx


class ItemUpdateView(UpdateView):
    model = Item
    fields = [
        "category", "name", "sku", "emoji", "image",
        "cost_price", "selling_price", "stock_qty", "low_stock_threshold", "is_active",
        "description",
    ]
    template_name = "inventory/item_form.html"
    success_url = reverse_lazy("inventory_dashboard")

    def dispatch(self, request, *args, **kwargs):
        branch = _get_branch(request)
        if not branch:
            return redirect("branch_select")
        self._branch = branch
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        self._save_sizes(form.instance)
        return response

    def _save_sizes(self, item):
        """Save size data from POST."""
        size_names = self.request.POST.getlist("size_name[]")
        size_prices = self.request.POST.getlist("size_price[]")
        size_retails = self.request.POST.getlist("size_retail_price[]")
        # Clear existing sizes and recreate
        item.sizes.all().delete()
        for i, name in enumerate(size_names):
            name = name.strip()
            if not name:
                continue
            price = size_prices[i] if i < len(size_prices) else "0"
            retail = size_retails[i] if i < len(size_retails) else ""
            try:
                kwargs = {
                    "name": name,
                    "price": Decimal(price),
                }
                if retail:
                    kwargs["retail_price"] = Decimal(retail)
                ItemSize.objects.create(item=item, **kwargs)
            except (ValueError, TypeError):
                pass

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_active"] = "inventory"
        ctx["categories"] = Category.objects.all().order_by("name")
        if self.object:
            ctx["sizes"] = self.object.sizes.all()
        return ctx


def sales_history(request):
    """List of completed transactions only."""
    branch = _get_branch(request)
    if not branch:
        return redirect("branch_select")
    transactions = Transaction.objects.filter(status="COMPLETED", branch=branch).order_by("-timestamp")[:100]
    return render(request, "pos/sales.html", {
        "nav_active": "sales",
        "transactions": transactions,
    })


def reports(request):
    """Reports dashboard with type selector, date range filter, and CSV export."""
    from .reports_engine import REPORT_OPTIONS

    report_type = request.GET.get("report", "daily_sales")
    format_type = request.GET.get("format", "html")

    from_raw = request.GET.get("from", "")
    to_raw = request.GET.get("to", "")
    from_date = None
    to_date = None
    from datetime import datetime
    for raw in [from_raw, to_raw]:
        if raw:
            try:
                dt = datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                pass
    if from_raw:
        try:
            from_date = datetime.strptime(from_raw, "%Y-%m-%d").date()
        except ValueError:
            pass
    if to_raw:
        try:
            to_date = datetime.strptime(to_raw, "%Y-%m-%d").date()
        except ValueError:
            pass

    opt = REPORT_OPTIONS.get(report_type)
    if opt is None:
        report_type = "daily_sales"
        opt = REPORT_OPTIONS[report_type]

    # CSV export
    if format_type == "csv":
        csv_fn = opt["csv_fn"]
        return csv_fn(from_date, to_date)

    # HTML render
    data = opt["fn"](from_date, to_date)

    context = {
        "nav_active": "reports",
        "report_type": report_type,
        "report_label": opt["label"],
        "report_emoji": opt["emoji"],
        "report_options": {k: {"label": v["label"], "emoji": v["emoji"]} for k, v in REPORT_OPTIONS.items()},
        "from_date": from_raw,
        "to_date": to_raw,
        "update_plan": json.dumps({
            "type": report_type,
            "from": from_raw,
            "to": to_raw,
        }),
    }

    context["report_data"] = data

    return render(request, "pos/reports.html", context)



# ===================== DASHBOARD CHARTS (Phase 2) =====================

@require_http_methods(["GET"])
@csrf_exempt
def dashboard_chart_data_api(request):
    """JSON endpoint returning chart data for D3.js dashboard."""
    from django.db.models import Sum, Count, Q
    from django.db.models.functions import TruncDate, TruncHour, ExtractHour
    from datetime import timedelta, date
    
    branch = _get_branch(request)
    if not branch:
        return JsonResponse({"error": "No branch selected"}, status=403)
    
    days = int(request.GET.get("days", 7))
    start_date = timezone.now().date() - timedelta(days=days - 1)
    
    completed = Transaction.objects.filter(
        status="COMPLETED", branch=branch,
        timestamp__gte=start_date
    )
    
    # Daily sales trend
    daily = completed.annotate(
        day=TruncDate("timestamp", tzinfo=timezone.get_current_timezone())
    ).values("day").annotate(
        total=Sum("grand_total"),
        count=Count("id")
    ).order_by("day")
    
    daily_sales = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        row = [x for x in daily if x["day"] == d]
        daily_sales.append({
            "date": d.isoformat(),
            "total": float(row[0]["total"]) if row else 0,
            "count": row[0]["count"] if row else 0
        })
    
    # Payment method breakdown
    pm = completed.values("payment_method").annotate(
        total=Sum("grand_total"),
        count=Count("id")
    ).order_by("-total")
    payment_methods = [
        {"method": p["payment_method"] or "OTHER", "total": float(p["total"]), "count": p["count"]}
        for p in pm
    ]
    
    # Top selling items
    top_items_qs = TransactionItem.objects.filter(
        transaction__in=completed
    ).values("item__name", "item__emoji").annotate(
        qty=Sum("quantity"),
        revenue=Sum("total_price")
    ).order_by("-qty")[:10]
    top_items = [
        {"name": t["item__name"], "emoji": t["item__emoji"] or "📦", "qty": t["qty"], "revenue": float(t["revenue"])}
        for t in top_items_qs
    ]
    
    # Sales by hour (today)
    hourly = completed.annotate(
        hour=ExtractHour("timestamp")
    ).values("hour").annotate(
        total=Sum("grand_total"),
        count=Count("id")
    ).order_by("hour")
    hourly_sales = {h: {"total": 0, "count": 0} for h in range(6, 23)}
    for h in hourly:
        if h["hour"] in hourly_sales:
            hourly_sales[h["hour"]] = {"total": float(h["total"]), "count": h["count"]}
    hourly_sales_list = [{"hour": h, **hourly_sales[h]} for h in sorted(hourly_sales.keys())]
    
    # Category breakdown
    cat_qs = TransactionItem.objects.filter(
        transaction__in=completed
    ).values("item__category__name").annotate(
        total=Sum("total_price"),
        qty=Sum("quantity")
    ).order_by("-total")
    categories = [
        {"name": c["item__category__name"], "total": float(c["total"]), "qty": c["qty"]}
        for c in cat_qs if c["item__category__name"]
    ]
    
    return JsonResponse({
        "daily_sales": daily_sales,
        "payment_methods": payment_methods,
        "top_items": top_items,
        "hourly_sales": hourly_sales_list,
        "categories": categories,
    })


def customers(request):
    """Customers page (placeholder — no login/auth)."""
    return render(request, "pos/customers.html", {
        "nav_active": "customers",
    })


def branch_list(request):
    branches = Branch.objects.all().order_by("type", "name")
    return render(request, "pos/branch_list.html", {
        "nav_active": "branches",
        "branches": branches,
    })


def branch_create(request):
    if request.method == "POST":
        Branch.objects.create(
            name=request.POST["name"],
            type=request.POST["type"],
            code=request.POST["code"],
            tax_rate=request.POST.get("tax_rate", 12),
            currency=request.POST.get("currency", "PHP"),
            address=request.POST.get("address", ""),
            contact=request.POST.get("contact", ""),
            notes=request.POST.get("notes", ""),
        )
        return redirect("branch_list")
    return render(request, "pos/branch_form.html", {
        "nav_active": "branches",
        "title": "Add Branch",
    })


def branch_update(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == "POST":
        branch.name = request.POST["name"]
        branch.type = request.POST["type"]
        branch.code = request.POST["code"]
        branch.tax_rate = request.POST.get("tax_rate", 12)
        branch.currency = request.POST.get("currency", "PHP")
        branch.address = request.POST.get("address", "")
        branch.contact = request.POST.get("contact", "")
        branch.notes = request.POST.get("notes", "")
        branch.is_active = request.POST.get("is_active") == "on"
        branch.save()
        return redirect("branch_list")
    return render(request, "pos/branch_form.html", {
        "nav_active": "branches",
        "title": "Edit Branch",
        "branch": branch,
    })


def branch_delete(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == "POST":
        branch.delete()
        return redirect("branch_list")
    return render(request, "pos/branch_confirm_delete.html", {
        "nav_active": "branches",
        "branch": branch,
    })


def product_catalog(request):
    """Full product catalog view with optional subcategory filter."""
    branch = _get_branch(request)
    if not branch:
        return redirect("branch_select")
    items = Item.objects.filter(is_active=True, branch=branch).select_related("category", "meal_subcategory").order_by("category__name", "name")
    subcategory_slug = request.GET.get("subcategory")
    if subcategory_slug:
        items = items.filter(meal_subcategory__slug=subcategory_slug)
    subcategories = MealSubcategory.objects.all()
    return render(request, "pos/products.html", {
        "nav_active": "products",
        "items": items,
        "subcategories": subcategories,
        "current_subcategory": subcategory_slug or "",
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
        table_number = payload.get("table_number", None)
        if table_number is not None:
            table_number = int(table_number)
        order_type = payload.get("order_type", "DINE_IN")

        # Normalize: frontend sends 'quantity', engine reads 'qty'
        cart = []
        for entry in raw_cart:
            qty = entry.get("quantity") or entry.get("qty")
            cart.append({"item_id": entry["item_id"], "qty": qty})

        if not cart:
            return JsonResponse({"status": "error", "message": "Cart empty"}, status=400)

        vat_inclusive = payload.get("vat_inclusive", True)
        if isinstance(vat_inclusive, str):
            vat_inclusive = vat_inclusive.lower() in ("true", "1", "yes")

        manual_discount_pct = payload.get("manual_discount_pct", None)
        if manual_discount_pct is not None:
            manual_discount_pct = Decimal(str(manual_discount_pct))

        shift_id = payload.get("shift_id", None)

        engine = CheckoutEngine(
            cart_data=cart,
            discount_id=discount_id,
            payment_method=pay_method,
            ref_num=ref_num,
            total_diners=diners,
            special_count=specials,
            table_number=table_number,
            order_type=order_type,
            vat_inclusive=vat_inclusive,
            manual_discount_pct=manual_discount_pct,
        )

        executed_txn = engine.process()

        # Assign branch + optionally shift
        branch = _get_branch(request)
        if branch:
            executed_txn.branch = branch
            executed_txn.save(update_fields=["branch"])

        if shift_id is not None:
            try:
                shift = Shift.objects.get(id=shift_id)
                executed_txn.shift = shift
                executed_txn.save(update_fields=["shift"])
            except Shift.DoesNotExist:
                pass

        return JsonResponse({
            "status": "success",
            "transaction_id": executed_txn.id,
            "grand_total": str(executed_txn.grand_total),
            "discount_amount": str(executed_txn.discount_amount),
            "manual_discount_pct": str(executed_txn.manual_discount_pct) if executed_txn.manual_discount_pct is not None else None,
        })

    except ValueError as val_err:
        return JsonResponse({"status": "error", "message": str(val_err)}, status=400)


# ===================== SIZE API =====================

@require_http_methods(["GET"])
def item_sizes_api(request, item_id):
    """JSON API returning sizes for a given item."""
    item = get_object_or_404(Item, pk=item_id)
    result = []
    for s in item.sizes.all():
        result.append({
            "name": s.name,
            "price": str(s.price),
            "retail_price": str(s.get_retail_price()),
        })
    return JsonResponse(result, safe=False)


# ===================== SHIFT API =====================

@csrf_exempt
def shift_start_api(request):
    """Start a new shift (offline — no login required)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        payload = json.loads(request.body)
        starting_float = Decimal(str(payload.get("starting_float", "0.00")))
        cashier_name = payload.get("cashier_name", "Offline User")
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON or float value"}, status=400)

    # Check for an existing open shift
    if Shift.objects.filter(cashier__username=cashier_name, status=Shift.Status.OPEN).exists():
        return JsonResponse({"error": "An open shift already exists"}, status=409)

    # Get or create User + Staff record for offline usage
    user, _ = User.objects.get_or_create(username=cashier_name)
    Staff.objects.get_or_create(
        user=user,
        defaults={"role": Staff.Role.ADMIN}
    )

    branch = _get_branch(request)
    shift = Shift.objects.create(
        cashier=user,
        branch=branch,
        starting_float=starting_float,
    )

    return JsonResponse({
        "id": shift.id,
        "cashier": shift.cashier.username,
        "start_time": shift.start_time.isoformat(),
        "end_time": None,
        "starting_float": str(shift.starting_float),
        "ending_float": None,
        "status": shift.status,
    }, status=201)


@csrf_exempt
def shift_end_api(request, shift_id):
    """Close a shift with ending cash float."""
    if request.method != "PUT":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    shift = get_object_or_404(Shift, id=shift_id)

    if shift.status == Shift.Status.CLOSED:
        return JsonResponse({"error": "Shift is already closed"}, status=409)

    try:
        payload = json.loads(request.body)
        ending_float_str = payload.get("ending_float")
        if ending_float_str is None:
            return JsonResponse({"error": "ending_float is required"}, status=400)
        ending_float = Decimal(str(ending_float_str))
        if ending_float < Decimal("0.00"):
            return JsonResponse({"error": "ending_float must be non-negative"}, status=400)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON or float value"}, status=400)

    from django.utils import timezone
    shift.ending_float = ending_float
    shift.end_time = timezone.now()
    shift.status = Shift.Status.CLOSED
    shift.save()

    return JsonResponse({
        "id": shift.id,
        "cashier": shift.cashier.username if shift.cashier else None,
        "start_time": shift.start_time.isoformat(),
        "end_time": shift.end_time.isoformat(),
        "starting_float": str(shift.starting_float),
        "ending_float": str(shift.ending_float),
        "status": shift.status,
    })


def shift_current_api(request):
    """Get the current open shift for the selected branch (no auth required)."""
    branch = _get_branch(request)
    if not branch:
        return JsonResponse({}, status=204)
    shift = Shift.objects.filter(status=Shift.Status.OPEN, branch=branch).first()
    if not shift:
        return JsonResponse({}, status=204)

    return JsonResponse({
        "id": shift.id,
        "cashier": shift.cashier.username,
        "start_time": shift.start_time.isoformat(),
        "end_time": None,
        "starting_float": str(shift.starting_float),
        "ending_float": None,
        "status": shift.status,
    })


@csrf_exempt
def shift_cash_count_api(request, shift_id):
    """
    GET/POST /api/shifts/<shift_id>/cash-count/

    GET: Return all cash count entries and computed total for a shift.
    POST: Replace all cash count entries for a shift with new denominations.
    """
    shift = get_object_or_404(Shift, id=shift_id)

    if request.method == "GET":
        entries = CashCount.objects.filter(shift=shift).order_by("-denomination_value")
        total = (entries.aggregate(
            total=dj_models.Sum("subtotal")
        )["total"] or Decimal("0.00")).quantize(Decimal("0.01"))
        return JsonResponse({
            "entries": [
                {
                    "id": e.id,
                    "denomination_value": str(e.denomination_value),
                    "quantity": e.quantity,
                    "subtotal": str(e.subtotal),
                }
                for e in entries
            ],
            "total_counted": str(total),
        })

    elif request.method == "POST":
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        denominations = payload.get("denominations", [])

        # Replace all entries for this shift
        CashCount.objects.filter(shift=shift).delete()

        entry_count = 0
        total_counted = Decimal("0.00")
        for denom in denominations:
            value = Decimal(str(denom["value"]))
            qty = int(denom["qty"])
            entry = CashCount.objects.create(
                shift=shift,
                denomination_value=value,
                quantity=qty,
            )
            entry_count += 1
            total_counted += entry.subtotal

        return JsonResponse({
            "entry_count": entry_count,
            "total_counted": str(total_counted),
        }, status=201)

    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)


def receipt(request, pk):
    """Receipt view for a completed transaction."""
    txn = get_object_or_404(Transaction.objects.prefetch_related("line_items__item"), pk=pk)
    return render(request, "pos/receipt.html", {
        "transaction": txn,
    })


def receipt_print(request, pk):
    """Printer-friendly receipt for thermal printers (80mm/58mm paper)."""
    txn = get_object_or_404(Transaction.objects.prefetch_related("line_items__item"), pk=pk)
    return render(request, "pos/receipt_print.html", {
        "transaction": txn,
    })


# ===================== KITCHEN ORDER TICKET =====================


def kot_print(request, pk):
    """Kitchen Order Ticket — food prep instructions only, no pricing."""
    txn = get_object_or_404(
        Transaction.objects.prefetch_related("line_items__item"),
        pk=pk,
    )
    items = txn.line_items.select_related("item").all()
    return render(request, "pos/kot_print.html", {
        "transaction": txn,
        "items": items,
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
            ctx["error"] = f"Cannot delete: {kwargs['protected_count']} item(s) are linked to this category."
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
        """Void a completed transaction (offline — no permission check)."""
        txn = get_object_or_404(Transaction.objects.prefetch_related("line_items__item"), pk=pk)

        if txn.status != "COMPLETED":
            return redirect("sales_history")

        # Parse reason from POST body
        reason = request.POST.get("reason", "").strip()

        now = timezone.now()

        for line in txn.line_items.all():
            line.item.stock_qty += line.quantity
            line.item.save()

        txn.status = "VOIDED"
        txn.void_reason = reason or None
        txn.voided_at = now
        txn.grand_total = Decimal("0.00")
        txn.discount_amount = Decimal("0.00")
        txn.save()

        return redirect("sales_history")


# ===================== EXPENSE API =====================

@csrf_exempt
def shift_expense_list_create_api(request, shift_id):
    """
    GET/POST /api/shifts/<shift_id>/expenses/

    GET: Return all expenses for a shift.
    POST: Record a new expense for the shift.
    """
    shift = get_object_or_404(Shift, id=shift_id)

    if request.method == "GET":
        entries = Expense.objects.filter(shift=shift).order_by("-created_at")
        total = entries.aggregate(
            total=dj_models.Sum("amount")
        )["total"] or Decimal("0.00")
        return JsonResponse({
            "expenses": [
                {
                    "id": e.id,
                    "amount": str(e.amount),
                    "description": e.description,
                    "category": e.category,
                    "created_at": e.created_at.isoformat(),
                }
                for e in entries
            ],
            "total_expenses": str(total.quantize(Decimal("0.01"))),
        })

    elif request.method == "POST":
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        amount_str = payload.get("amount")
        description = payload.get("description")
        category = payload.get("category", None)

        if not amount_str:
            return JsonResponse({"error": "amount is required"}, status=400)
        if not description:
            return JsonResponse({"error": "description is required"}, status=400)

        try:
            amount = Decimal(str(amount_str))
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid amount"}, status=400)

        expense = Expense.objects.create(
            shift=shift,
            amount=amount,
            description=description,
            category=category if category else None,
        )

        return JsonResponse({
            "id": expense.id,
            "amount": str(expense.amount),
            "description": expense.description,
            "category": expense.category,
            "created_at": expense.created_at.isoformat(),
        }, status=201)

    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)


# ===================== SHIFT REPORTING: X-READ / Z-READ =====================


def _build_shift_report(shift):
    """Build a report dict for a given shift (shared between X-Read and Z-Read)."""
    # Completed transactions totals
    completed_txns = shift.transactions.filter(status="COMPLETED")
    total_sales = completed_txns.aggregate(
        total=dj_models.Sum("grand_total")
    )["total"] or Decimal("0.00")

    # Payment breakdown
    pmt_totals = (
        completed_txns
        .values("payment_method")
        .annotate(
            total=dj_models.Sum("grand_total"),
            count=dj_models.Count("id"),
        )
        .order_by("payment_method")
    )
    payment_breakdown = [
        {
            "method": entry["payment_method"],
            "total": str(entry["total"].quantize(Decimal("0.01"))),
            "count": entry["count"],
        }
        for entry in pmt_totals
    ]

    # Expenses
    expenses_qs = shift.expenses.all().order_by("-created_at")
    total_expenses = expenses_qs.aggregate(
        total=dj_models.Sum("amount")
    )["total"] or Decimal("0.00")

    expenses_list = [
        {
            "id": e.id,
            "amount": str(e.amount),
            "description": e.description,
            "category": e.category,
            "created_at": e.created_at.isoformat(),
        }
        for e in expenses_qs
    ]

    # Cash count totals
    cc_qs = shift.cash_counts.all()
    total_counted = cc_qs.aggregate(
        total=dj_models.Sum("subtotal")
    )["total"] or Decimal("0.00")

    # Expected cash = starting float + cash sales - expenses
    cash_sales = completed_txns.filter(payment_method="CASH").aggregate(
        total=dj_models.Sum("grand_total")
    )["total"] or Decimal("0.00")
    expected_cash = shift.starting_float + cash_sales - total_expenses

    # Variance = counted - expected
    variance = total_counted - expected_cash

    net_sales = total_sales - total_expenses

    return {
        "shift_id": shift.id,
        "status": shift.status,
        "start_time": shift.start_time.isoformat(),
        "end_time": shift.end_time.isoformat() if shift.end_time else None,
        "starting_float": str(shift.starting_float.quantize(Decimal("0.01"))),
        "total_sales": str(total_sales.quantize(Decimal("0.01"))),
        "net_sales": str(net_sales.quantize(Decimal("0.01"))),
        "payment_breakdown": payment_breakdown,
        "total_expenses": str(total_expenses.quantize(Decimal("0.01"))),
        "expenses": expenses_list,
        "total_counted": str(total_counted.quantize(Decimal("0.01"))),
        "expected_cash": str(expected_cash.quantize(Decimal("0.01"))),
        "variance": str(variance.quantize(Decimal("0.01"))),
    }


def shift_x_read_api(request, shift_id):
    """
    GET /api/shifts/<shift_id>/x-read/

    Interim shift report — does NOT close the shift.
    Returns sales summary, payment breakdown, expenses, cash count info.
    """
    shift = get_object_or_404(Shift, id=shift_id)
    report = _build_shift_report(shift)
    return JsonResponse(report)


@require_http_methods(["GET"])
def shift_z_read_api(request, shift_id):
    """
    GET /api/shifts/<shift_id>/z-read/

    Final shift report — closes the shift.
    Same report structure as X-Read but also updates the shift:
      - status -> CLOSED
      - end_time -> now
    """
    shift = get_object_or_404(Shift, id=shift_id)

    if shift.status == Shift.Status.CLOSED:
        return JsonResponse(
            {"error": "Shift is already closed"}, status=409
        )

    # Close the shift
    from django.utils import timezone
    shift.status = Shift.Status.CLOSED
    shift.end_time = timezone.now()
    shift.save()

    report = _build_shift_report(shift)
    return JsonResponse(report)


def shift_report_print(request, shift_id):
    """
    GET /api/shifts/<shift_id>/report/print/

    Printable HTML view of the shift report.
    Accepts ?type=xread or ?type=zread query param to label the report.
    """
    shift = get_object_or_404(Shift, id=shift_id)
    report = _build_shift_report(shift)
    report_type = request.GET.get("type", "xread")
    from django.utils import timezone as tz_util
    return render(request, "pos/shift_report_print.html", {
        "shift": shift,
        "report": report,
        "report_type": report_type,
        "generated_at": tz_util.now().strftime("%Y-%m-%d %H:%M"),
    })


# ---- Borrower (Phase 5: Product Lend) ----

def borrower_list(request):
    """List all borrower records for the current branch."""
    branch_id = request.session.get("current_branch_id")
    borrowers = Borrower.objects.filter(branch_id=branch_id).select_related("product")
    return render(request, "pos/borrower_list.html", {
        "borrowers": borrowers,
        "nav_active": "borrower",
    })


def borrower_add(request):
    """Add a new borrower record."""
    branch_id = request.session.get("current_branch_id")
    branch = Branch.objects.filter(id=branch_id).first()
    items = Item.objects.filter(branch_id=branch_id).order_by("name")

    if request.method == "POST":
        name = request.POST.get("name", "")
        product_id = request.POST.get("product")
        price = request.POST.get("price", "0")
        size = request.POST.get("size", "")
        qty = request.POST.get("qty", 1)
        date_borrowed = request.POST.get("date_borrowed")
        return_date = request.POST.get("return_date") or None
        contact = request.POST.get("contact", "")
        address = request.POST.get("address", "")
        receipt = request.FILES.get("receipt")

        product = Item.objects.filter(id=product_id).first() if product_id else None

        Borrower.objects.create(
            name=name,
            product=product,
            price=price,
            size=size,
            qty=qty,
            date_borrowed=date_borrowed,
            return_date=return_date,
            contact=contact,
            address=address,
            receipt=receipt,
            branch=branch,
        )
        return redirect("borrower_list")

    # GET: fetch items for the product dropdown, with their sizes
    items_with_sizes = []
    for item in items:
        item_size_list = list(item.sizes.all().values("name", "price"))
        items_with_sizes.append({
            "id": item.id,
            "name": item.name,
            "emoji": item.emoji or "📦",
            "selling_price": float(item.selling_price),
            "sizes": [{"name": s["name"], "price": float(s["price"])} for s in item_size_list],
        })

    return render(request, "pos/borrower_add.html", {
        "items": items,
        "items_json": json.dumps(items_with_sizes),
        "branch": branch,
        "today": date.today().isoformat(),
        "nav_active": "borrower",
    })
