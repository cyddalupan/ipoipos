from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("inventory/", views.InventoryDashboardView.as_view(), name="inventory_dashboard"),
    path("inventory/add/", views.ItemCreateView.as_view(), name="item_add"),
    path("inventory/<pk>/edit/", views.ItemUpdateView.as_view(), name="item_edit"),
    path("sales/", views.sales_history, name="sales_history"),
    path("reports/", views.reports, name="reports"),
    path("customers/", views.customers, name="customers"),
    path("products/", views.product_catalog, name="product_catalog"),
    path("api/checkout/", views.checkout_submit_api, name="checkout_api"),
    path("receipt/<pk>/", views.receipt, name="receipt"),

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
]
