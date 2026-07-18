from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Category, Item, ItemSize, DiscountType, Transaction, TransactionItem, Staff, MealSubcategory, Shift, CashCount, Expense, Patient, Queue, Branch


class StaffInline(admin.StackedInline):
    """Inline Staff fields within the User admin page."""
    model = Staff
    can_delete = True
    verbose_name_plural = "Staff Profile"
    fk_name = "user"


class CustomUserAdmin(UserAdmin):
    """Extended UserAdmin with Staff inline role management."""
    inlines = [StaffInline]
    list_display = ("username", "email", "first_name", "last_name", "get_role", "is_staff")

    @admin.display(description="Role")
    def get_role(self, obj):
        try:
            return obj.staff.get_role_display()
        except Staff.DoesNotExist:
            return "—"

    def get_inline_instances(self, request, obj=None):
        """Only show Staff inline for existing users, not add form."""
        if not obj:
            return []
        return super().get_inline_instances(request, obj)


# Unregister default UserAdmin and register our custom version
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(MealSubcategory)
class MealSubcategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "emoji")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "meal_subcategory", "selling_price", "stock_qty", "is_active")
    list_filter = ("category", "meal_subcategory", "is_active")
    search_fields = ("name", "sku")


@admin.register(ItemSize)
class ItemSizeAdmin(admin.ModelAdmin):
    list_display = ("item", "name", "price", "retail_price")
    list_filter = ("item__category",)
    search_fields = ("name", "item__name")


@admin.register(DiscountType)
class DiscountTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "value", "is_active")
    list_filter = ("kind", "is_active")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "timestamp", "grand_total", "payment_method", "status", "void_reason")
    list_filter = ("status", "payment_method")
    readonly_fields = ("subtotal", "vat_exclusive_sales", "vat_amount", "grand_total", "voided_at")


@admin.register(TransactionItem)
class TransactionItemAdmin(admin.ModelAdmin):
    list_display = ("transaction", "item", "quantity", "unit_price", "total_price")


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("id", "cashier", "start_time", "end_time", "starting_float", "ending_float", "status")
    list_filter = ("status",)
    readonly_fields = ("start_time",)


@admin.register(CashCount)
class CashCountAdmin(admin.ModelAdmin):
    list_display = ("id", "shift", "denomination_value", "quantity", "subtotal")
    list_filter = ("shift",)
    readonly_fields = ("subtotal",)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("id", "shift", "amount", "description", "category", "created_at")
    list_filter = ("shift", "category")
    readonly_fields = ("created_at",)


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("name", "fb_psid", "created_at", "updated_at")
    search_fields = ("name", "fb_psid")


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "type", "tax_rate", "currency", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("name", "code")


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = ("patient", "status", "service", "service_area", "created_at")
    list_filter = ("status",)
    search_fields = ("patient__name", "patient__fb_psid")
