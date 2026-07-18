"""
Reports engine for CASSEY POS.

Provides query and CSV-generation logic for all report types:
  - Daily sales (itemized by meal category)
  - Shift sales
  - Expense per shift
  - Best-selling items
  - Peak hours (transaction count per hour)
"""

import csv
import io
from decimal import Decimal

from django.db import models as dj_models
from django.db.models import Q, Sum, Count
from django.http import StreamingHttpResponse
from django.utils import timezone as tz_util

from .models import Transaction, TransactionItem, Shift, Expense


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _completed_txns_qs(from_date=None, to_date=None):
    """Return a QuerySet of COMPLETED transactions optionally date-filtered.

    *from_date* and *to_date* are date or datetime objects (inclusive).
    When both are None the full dataset is returned.
    """
    qs = Transaction.objects.filter(status="COMPLETED")
    if from_date:
        qs = qs.filter(timestamp__date__gte=from_date)
    if to_date:
        qs = qs.filter(timestamp__date__lte=to_date)
    return qs


def _date_filter_kwargs(from_date=None, to_date=None):
    """Return dict to pass to template context for 'current' filter values."""
    return {
        "from_date": str(from_date) if from_date else "",
        "to_date": str(to_date) if to_date else "",
    }


# ---------------------------------------------------------------------------
# 1. Daily Sales Report (itemized by meal category)
# ---------------------------------------------------------------------------

def daily_sales_report(from_date=None, to_date=None):
    """Return dict with daily sales data grouped by meal category.

    Returns::
        {
            "grouped": [
                {"category": "Chicken", "emoji": "🍗",
                 "items": [{"name": "Fried Chicken 1pc", "emoji": "🍗",
                            "qty": 15, "total": 3000.00}, ...],
                 "category_qty": 20, "category_total": 4000.00},
            ],
            "grand_total": ...,
        }
    """
    txn_ids = _completed_txns_qs(from_date, to_date).values_list("id", flat=True)
    line_items = (
        TransactionItem.objects
        .filter(transaction_id__in=txn_ids)
        .select_related("item__category", "item__meal_subcategory")
        .all()
    )

    # Aggregate per (category_name, category_emoji, item_name, item_emoji)
    from collections import defaultdict
    cat_map = defaultdict(lambda: defaultdict(lambda: {"qty": 0, "total": Decimal("0.00")}))

    for li in line_items:
        item = li.item
        cat = item.category
        cat_name = cat.name
        # Use MealSubcategory emoji as category emoji, or fallback to 📋
        cat_emoji = item.meal_subcategory.emoji if item.meal_subcategory and item.meal_subcategory.emoji else ""
        item_name = item.name
        item_emoji = item.emoji or ""
        cat_map[(cat_name, cat_emoji)][(item_name, item_emoji)]["qty"] += li.quantity
        cat_map[(cat_name, cat_emoji)][(item_name, item_emoji)]["total"] += li.total_price

    # Get category totals
    cat_totals = (
        TransactionItem.objects
        .filter(transaction_id__in=txn_ids)
        .values("item__category__name")
        .annotate(
            total_qty=Sum("quantity"),
            total_sales=Sum("total_price"),
        )
        .order_by("-total_sales")
    )
    cat_total_map = {}
    for ct in cat_totals:
        cat_total_map[ct["item__category__name"]] = {
            "qty": ct["total_qty"],
            "total": ct["total_sales"],
        }

    grouped = []
    all_totals = TransactionItem.objects.filter(transaction_id__in=txn_ids).aggregate(
        qty=Sum("quantity"),
        sales=Sum("total_price"),
    )
    grand_qty = all_totals["qty"] or 0
    grand_total = all_totals["sales"] or Decimal("0.00")

    # Sort categories by total sales descending
    sorted_cats = sorted(cat_map.items(), key=lambda x: cat_total_map.get(x[0][0], {}).get("total", Decimal("0.00")), reverse=True)

    for (cat_name, cat_emoji), items_dict in sorted_cats:
        items_list = [
            {
                "name": iname,
                "emoji": iemoji or "📦",
                "qty": data["qty"],
                "total": data["total"],
            }
            for (iname, iemoji), data in sorted(items_dict.items(), key=lambda x: x[1]["total"], reverse=True)
        ]
        cat_info = cat_total_map.get(cat_name, {"qty": 0, "total": Decimal("0.00")})
        grouped.append({
            "category": cat_name,
            "emoji": cat_emoji or "📋",
            "items": items_list,
            "category_qty": cat_info["qty"],
            "category_total": cat_info["total"],
        })

    return {
        "grouped": grouped,
        "grand_qty": grand_qty,
        "grand_total": grand_total,
    }


def daily_sales_csv(from_date=None, to_date=None):
    """Return StreamingHttpResponse for daily sales CSV."""
    data = daily_sales_report(from_date, to_date)

    pseudo_buffer = io.StringIO()
    writer = csv.writer(pseudo_buffer)

    rows = []
    rows.append(["Daily Sales Report"])
    if from_date:
        rows.append(["From:", str(from_date)])
    if to_date:
        rows.append(["To:", str(to_date)])
    rows.append([])

    for group in data["grouped"]:
        rows.append([f"{group['emoji']} {group['category']}", "", "Qty", "Total"])
        for item in group["items"]:
            rows.append([
                f"{item['emoji']} {item['name']}",
                "",
                str(item["qty"]),
                f"₱{item['total']:.2f}",
            ])
        rows.append([
            f"  Subtotal ({group['category']})",
            "",
            str(group["category_qty"]),
            f"₱{group['category_total']:.2f}",
        ])
        rows.append([])

    rows.append(["GRAND TOTAL", "", str(data["grand_qty"]), f"₱{data['grand_total']:.2f}"])

    return _rows_to_csv_stream(rows, "daily_sales.csv")


# ---------------------------------------------------------------------------
# 2. Shift Sales Report
# ---------------------------------------------------------------------------

def shift_sales_report(from_date=None, to_date=None):
    """Return list of shifts with sales summary, filtered by shift start date."""
    qs = Shift.objects.all()
    if from_date:
        qs = qs.filter(start_time__date__gte=from_date)
    if to_date:
        qs = qs.filter(start_time__date__lte=to_date)
    qs = qs.order_by("-start_time")

    shifts_data = []
    total_all = Decimal("0.00")

    for shift in qs:
        completed = shift.transactions.filter(status="COMPLETED")
        sales = completed.aggregate(total=Sum("grand_total"))["total"] or Decimal("0.00")
        txn_count = completed.count()
        expenses = shift.expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        total_all += sales

        shifts_data.append({
            "id": shift.id,
            "cashier": shift.cashier.username if shift.cashier else "—",
            "start": shift.start_time.isoformat(),
            "end": shift.end_time.isoformat() if shift.end_time else "Open",
            "status": shift.status,
            "sales": sales,
            "expenses": expenses,
            "txn_count": txn_count,
        })

    return {
        "shifts": shifts_data,
        "total_sales": total_all,
    }


def shift_sales_csv(from_date=None, to_date=None):
    """CSV for shift sales."""
    data = shift_sales_report(from_date, to_date)
    rows = [
        ["Shift Sales Report"],
        *([f"From: {str(from_date)}"] if from_date else []),
        *([f"To: {str(to_date)}"] if to_date else []),
        [],
        ["Shift ID", "Cashier", "Start", "End", "Status", "Sales", "Expenses", "Transactions"],
    ]
    for s in data["shifts"]:
        rows.append([
            str(s["id"]),
            s["cashier"],
            s["start"],
            s["end"],
            s["status"],
            f"₱{s['sales']:.2f}",
            f"₱{s['expenses']:.2f}",
            str(s["txn_count"]),
        ])
    rows.append([])
    rows.append(["TOTAL", "", "", "", "", f"₱{data['total_sales']:.2f}", "", ""])
    return _rows_to_csv_stream(rows, "shift_sales.csv")


# ---------------------------------------------------------------------------
# 3. Expense Report per Shift
# ---------------------------------------------------------------------------

def expense_report(from_date=None, to_date=None):
    """Return expenses grouped by shift, filtered by expense created_at date."""
    qs = Expense.objects.select_related("shift__cashier").all()
    if from_date:
        qs = qs.filter(created_at__date__gte=from_date)
    if to_date:
        qs = qs.filter(created_at__date__lte=to_date)
    qs = qs.order_by("-created_at")

    expenses_list = []
    total_all = Decimal("0.00")

    for exp in qs:
        total_all += exp.amount
        expenses_list.append({
            "id": exp.id,
            "shift_id": exp.shift.id,
            "cashier": exp.shift.cashier.username if exp.shift.cashier else "—",
            "amount": exp.amount,
            "description": exp.description,
            "category": exp.category or "—",
            "created_at": exp.created_at.isoformat(),
        })

    # Group-by-shift summary
    grouped = (
        Expense.objects.all()
    )
    if from_date:
        grouped = grouped.filter(created_at__date__gte=from_date)
    if to_date:
        grouped = grouped.filter(created_at__date__lte=to_date)
    grouped = (
        grouped
        .values("shift_id")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-shift_id")
    )

    shift_summaries = []
    for g in grouped:
        shift_summaries.append({
            "shift_id": g["shift_id"],
            "total": g["total"],
            "count": g["count"],
        })

    return {
        "expenses": expenses_list,
        "total": total_all,
        "shift_summaries": shift_summaries,
    }


def expense_csv(from_date=None, to_date=None):
    """CSV for expense report."""
    data = expense_report(from_date, to_date)
    rows = [
        ["Expense Report"],
        *([f"From: {str(from_date)}"] if from_date else []),
        *([f"To: {str(to_date)}"] if to_date else []),
        [],
        ["ID", "Shift ID", "Cashier", "Amount", "Description", "Category", "Date"],
    ]
    for e in data["expenses"]:
        rows.append([
            str(e["id"]),
            str(e["shift_id"]),
            e["cashier"],
            f"₱{e['amount']:.2f}",
            e["description"],
            e["category"],
            e["created_at"],
        ])
    rows.append([])
    rows.append(["TOTAL", "", "", f"₱{data['total']:.2f}", "", "", ""])
    return _rows_to_csv_stream(rows, "expenses.csv")


# ---------------------------------------------------------------------------
# 4. Best-Selling Items
# ---------------------------------------------------------------------------

def best_selling_report(from_date=None, to_date=None, limit=20):
    """Return best-selling items sorted by quantity sold."""
    txn_ids = _completed_txns_qs(from_date, to_date).values_list("id", flat=True)

    items = (
        TransactionItem.objects
        .filter(transaction_id__in=txn_ids)
        .values("item__name", "item__emoji", "item__category__name")
        .annotate(
            total_qty=Sum("quantity"),
            total_sales=Sum("total_price"),
        )
        .order_by("-total_qty")[:limit]
    )

    results = []
    rank = 1
    for it in items:
        results.append({
            "rank": rank,
            "name": it["item__name"],
            "emoji": it["item__emoji"] or "📦",
            "category": it["item__category__name"],
            "qty": it["total_qty"],
            "sales": it["total_sales"],
        })
        rank += 1

    return {"items": results}


def best_selling_csv(from_date=None, to_date=None):
    """CSV for best-selling items."""
    data = best_selling_report(from_date, to_date)
    rows = [
        ["Best-Selling Items Report"],
        *([f"From: {str(from_date)}"] if from_date else []),
        *([f"To: {str(to_date)}"] if to_date else []),
        [],
        ["Rank", "Item", "Category", "Qty Sold", "Total Sales"],
    ]
    for it in data["items"]:
        rows.append([
            str(it["rank"]),
            f"{it['emoji']} {it['name']}",
            it["category"],
            str(it["qty"]),
            f"₱{it['sales']:.2f}",
        ])
    return _rows_to_csv_stream(rows, "best_selling.csv")


# ---------------------------------------------------------------------------
# 5. Peak Hours Report
# ---------------------------------------------------------------------------

def peak_hours_report(from_date=None, to_date=None):
    """Return transaction count grouped by hour of day (0-23)."""
    txn_qs = _completed_txns_qs(from_date, to_date)
    all_txns = list(txn_qs.values("timestamp"))

    hour_counts = {h: 0 for h in range(24)}
    hour_sales = {h: Decimal("0.00") for h in range(24)}

    for txn in all_txns:
        h = txn["timestamp"].hour
        hour_counts[h] += 1

    # Also sum sales per hour
    txn_with_sales = txn_qs.values("timestamp", "grand_total")
    for txn in txn_with_sales:
        h = txn["timestamp"].hour
        hour_sales[h] += txn["grand_total"]

    hours = []
    for h in range(24):
        label = f"{h:02d}:00"
        hours.append({
            "hour": h,
            "label": label,
            "count": hour_counts[h],
            "sales": hour_sales[h],
        })

    return {"hours": hours}


def peak_hours_csv(from_date=None, to_date=None):
    """CSV for peak hours report."""
    data = peak_hours_report(from_date, to_date)
    rows = [
        ["Peak Hours Report"],
        *([f"From: {str(from_date)}"] if from_date else []),
        *([f"To: {str(to_date)}"] if to_date else []),
        [],
        ["Hour", "Transactions", "Sales"],
    ]
    for h in data["hours"]:
        rows.append([
            h["label"],
            str(h["count"]),
            f"₱{h['sales']:.2f}",
        ])
    return _rows_to_csv_stream(rows, "peak_hours.csv")


# ---------------------------------------------------------------------------
# CSV streaming helper
# ---------------------------------------------------------------------------

class EchoBuffer:
    """An in-memory writeable object compatible with csv.writer."""

    def write(self, value):
        return value


def _rows_to_csv_stream(rows, filename):
    """Return a StreamingHttpResponse with a CSV file attachment."""
    from django.http import StreamingHttpResponse

    def stream():
        pseudo = EchoBuffer()
        writer = csv.writer(pseudo)
        for row in rows:
            yield writer.writerow(row)

    response = StreamingHttpResponse(
        streaming_content=stream(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# Dispatch helper for views
# ---------------------------------------------------------------------------

REPORT_OPTIONS = {
    "daily_sales": {
        "label": "Daily Sales",
        "emoji": "📅",
        "fn": daily_sales_report,
        "csv_fn": daily_sales_csv,
    },
    "shift_sales": {
        "label": "Shift Sales",
        "emoji": "🔄",
        "fn": shift_sales_report,
        "csv_fn": shift_sales_csv,
    },
    "expenses": {
        "label": "Expenses",
        "emoji": "💸",
        "fn": expense_report,
        "csv_fn": expense_csv,
    },
    "best_selling": {
        "label": "Best Sellers",
        "emoji": "🏆",
        "fn": best_selling_report,
        "csv_fn": best_selling_csv,
    },
    "peak_hours": {
        "label": "Peak Hours",
        "emoji": "⏰",
        "fn": peak_hours_report,
        "csv_fn": peak_hours_csv,
    },
}
