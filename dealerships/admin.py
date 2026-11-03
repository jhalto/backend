from django.contrib import admin

from .models import (
    ActivityLog, Business, BusinessUser, Contact, Expense, Location, Payment,
    PaymentAllocation, Product, ProductCategory, Purchase, PurchaseLine, Sale,
    SaleLine, SaleReturn, SaleReturnLine, PurchaseReturn, PurchaseReturnLine,
    StockMovement, StockTransfer, StockTransferLine,
)


class LineInline(admin.TabularInline):
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('purchase_number', 'business', 'supplier', 'location', 'status', 'purchase_date', 'grand_total')
    list_filter = ('status', 'purchase_date')
    search_fields = ('purchase_number', 'supplier__display_name')
    inlines = [type('PurchaseLineInline', (LineInline,), {'model': PurchaseLine})]


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('sale_number', 'business', 'customer', 'location', 'status', 'sale_date', 'grand_total')
    list_filter = ('status', 'sale_date')
    search_fields = ('sale_number', 'customer__display_name')
    inlines = [type('SaleLineInline', (LineInline,), {'model': SaleLine})]


for model in (Business, BusinessUser, Location, ProductCategory, Product, Contact,
              StockTransfer, StockTransferLine, StockMovement, Payment,
              PaymentAllocation, Expense, ActivityLog, SaleReturn, SaleReturnLine,
              PurchaseReturn, PurchaseReturnLine):
    admin.site.register(model)
