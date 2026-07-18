from django.urls import path
from . import views

urlpatterns = [
    path("", views.branch_select, name="branch_select"),
    path("pos/", views.home, name="home"),
    path("pos/order/", views.pos_order, name="pos_page"),
    path("switch-branch/", views.branch_switch, name="branch_switch"),
    path("inventory/", views.InventoryDashboardView.as_view(), name="inventory_dashboard"),
    path("inventory/add/", views.ItemCreateView.as_view(), name="item_add"),
    path("inventory/<pk>/edit/", views.ItemUpdateView.as_view(), name="item_edit"),
    path("sales/", views.sales_history, name="sales_history"),
    path("reports/", views.reports, name="reports"),
    path("customers/", views.customers, name="customers"),
    path("products/", views.product_catalog, name="product_catalog"),
    path("api/checkout/", views.checkout_submit_api, name="checkout_api"),
    path("receipt/<pk>/", views.receipt, name="receipt"),
    path("receipt/<pk>/print/", views.receipt_print, name="receipt_print"),
    path("kot/<pk>/print/", views.kot_print, name="kot_print"),

    # Category CRUD
    path("categories/", views.CategoryListView.as_view(), name="category_list"),
    path("categories/add/", views.CategoryCreateView.as_view(), name="category_add"),
    path("categories/<pk>/edit/", views.CategoryUpdateView.as_view(), name="category_edit"),
    path("categories/<pk>/delete/", views.CategoryDeleteView.as_view(), name="category_delete"),

    # DiscountType CRUD
    path("discounts/", views.DiscountTypeListView.as_view(), name="discount_list"),
    path("discounts/add/", views.DiscountTypeCreateView.as_view(), name="discount_add"),
    path("discounts/<pk>/edit/", views.DiscountTypeUpdateView.as_view(), name="discount_edit"),
    path("discounts/<pk>/delete/", views.DiscountTypeDeleteView.as_view(), name="discount_delete"),

    # Item Delete + Stock Adjust
    path("inventory/<pk>/delete/", views.ItemDeleteView.as_view(), name="item_delete"),
    path("inventory/<pk>/stock-adjust/", views.InventoryStockAdjustView.as_view(), name="stock_adjust"),

    # Transaction Void
    path("transactions/<pk>/void/", views.TransactionVoidView.as_view(), name="transaction_void"),

    # Item Sizes API
    path("api/items/<int:item_id>/sizes/", views.item_sizes_api, name="item_sizes_api"),

    # Shift API
    path("api/shifts/start/", views.shift_start_api, name="shift_start_api"),
    path("api/shifts/<int:shift_id>/end/", views.shift_end_api, name="shift_end_api"),
    path("api/shifts/current/", views.shift_current_api, name="shift_current_api"),
    path("api/shifts/<int:shift_id>/cash-count/", views.shift_cash_count_api, name="shift_cash_count_api"),
    path("api/shifts/<int:shift_id>/expenses/", views.shift_expense_list_create_api, name="shift_expenses_api"),

    # Branches
    path("branches/", views.branch_list, name="branch_list"),
    path("branches/add/", views.branch_create, name="branch_add"),
    path("branches/<pk>/edit/", views.branch_update, name="branch_edit"),
    path("branches/<pk>/delete/", views.branch_delete, name="branch_delete"),

    # Shift Reports
    path("api/shifts/<int:shift_id>/x-read/", views.shift_x_read_api, name="shift_x_read"),
    path("api/shifts/<int:shift_id>/z-read/", views.shift_z_read_api, name="shift_z_read"),
    path("api/shifts/<int:shift_id>/report/print/", views.shift_report_print, name="shift_report_print"),
    # Dashboard Charts
    path("api/dashboard/chart-data/", views.dashboard_chart_data_api, name="dashboard_chart_data_api"),

    # Borrower (Phase 5: Product Lend)
    path("borrowers/", views.borrower_list, name="borrower_list"),
    path("borrowers/add/", views.borrower_add, name="borrower_add"),
]