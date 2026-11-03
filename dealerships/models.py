import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Business(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    currency_code = models.CharField(max_length=3, default='BDT')
    timezone = models.CharField(max_length=64, default='Asia/Dhaka')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class BusinessUser(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        MANAGER = 'MANAGER', 'Manager'
        SALES = 'SALES', 'Sales'
        STOCK = 'STOCK', 'Stock'
        ACCOUNTS = 'ACCOUNTS', 'Accounts'

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='business_memberships')
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.SALES)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['business', 'user'], name='uniq_business_user')]


class Location(TimeStampedModel):
    class Kind(models.TextChoices):
        BRANCH = 'BRANCH', 'Branch'
        WAREHOUSE = 'WAREHOUSE', 'Warehouse'
        BOTH = 'BOTH', 'Branch and warehouse'

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=32)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.BOTH)
    address = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['business', 'code'], name='uniq_location_code_per_business'),
            models.UniqueConstraint(fields=['business'], condition=Q(is_default=True), name='uniq_default_location_per_business'),
        ]

    def __str__(self):
        return f'{self.business}: {self.name}'


class ProductCategory(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=120)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='children')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [models.UniqueConstraint(fields=['business', 'name'], name='uniq_category_name_per_business')]

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(ProductCategory, null=True, blank=True, on_delete=models.PROTECT, related_name='products')
    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit_name = models.CharField(max_length=32, default='piece')
    purchase_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [models.UniqueConstraint(fields=['business', 'sku'], name='uniq_product_sku_per_business')]

    def __str__(self):
        return f'{self.sku} · {self.name}'


class Contact(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='contacts')
    display_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_customer = models.BooleanField(default=False)
    is_supplier = models.BooleanField(default=False)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                          help_text='Positive means receivable; negative means payable.')
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return self.display_name


class Purchase(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        RECEIVED = 'RECEIVED', 'Received'
        PARTIALLY_RETURNED = 'PARTIALLY_RETURNED', 'Partially returned'
        RETURNED = 'RETURNED', 'Returned'
        VOID = 'VOID', 'Void'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='purchases')
    supplier = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name='purchases')
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='purchases')
    purchase_number = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    purchase_date = models.DateField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='created_purchases')
    reverses_purchase = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='reversal_documents')

    class Meta:
        ordering = ['-purchase_date', '-created_at']
        constraints = [models.UniqueConstraint(fields=['business', 'purchase_number'], name='uniq_purchase_number_per_business')]


class PurchaseLine(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='purchase_lines')
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='purchase_lines')
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)
    product_name_snapshot = models.CharField(max_length=200)
    sku_snapshot = models.CharField(max_length=64)


class PurchaseReturn(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='purchase_returns')
    purchase = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name='returns')
    return_number = models.CharField(max_length=40)
    return_date = models.DateField()
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['business', 'return_number'], name='uniq_purchase_return_number_per_business')]


class PurchaseReturnLine(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='purchase_return_lines')
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, related_name='lines')
    purchase_line = models.ForeignKey(PurchaseLine, on_delete=models.PROTECT, related_name='return_lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='purchase_return_lines')
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)
    product_name_snapshot = models.CharField(max_length=200)
    sku_snapshot = models.CharField(max_length=64)


class Sale(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        COMPLETED = 'COMPLETED', 'Completed'
        PARTIALLY_RETURNED = 'PARTIALLY_RETURNED', 'Partially returned'
        RETURNED = 'RETURNED', 'Returned'
        VOID = 'VOID', 'Void'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.PROTECT, related_name='sales')
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='sales')
    sale_number = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    sale_date = models.DateField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='created_sales')
    reverses_sale = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='reversal_documents')

    class Meta:
        ordering = ['-sale_date', '-created_at']
        constraints = [models.UniqueConstraint(fields=['business', 'sale_number'], name='uniq_sale_number_per_business')]


class SaleLine(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='sale_lines')
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_lines')
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)
    product_name_snapshot = models.CharField(max_length=200)
    sku_snapshot = models.CharField(max_length=64)


class SaleReturn(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='sale_returns')
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='returns')
    return_number = models.CharField(max_length=40)
    return_date = models.DateField()
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['business', 'return_number'], name='uniq_sale_return_number_per_business')]


class SaleReturnLine(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='sale_return_lines')
    sale_return = models.ForeignKey(SaleReturn, on_delete=models.CASCADE, related_name='lines')
    sale_line = models.ForeignKey(SaleLine, on_delete=models.PROTECT, related_name='return_lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_return_lines')
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)
    product_name_snapshot = models.CharField(max_length=200)
    sku_snapshot = models.CharField(max_length=64)


class StockTransfer(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        COMPLETED = 'COMPLETED', 'Completed'
        VOID = 'VOID', 'Void'

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='stock_transfers')
    transfer_number = models.CharField(max_length=40)
    source_location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='transfers_out')
    destination_location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='transfers_in')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    transfer_date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['business', 'transfer_number'], name='uniq_transfer_number_per_business')]

    def clean(self):
        if self.source_location_id and self.destination_location_id and self.source_location_id == self.destination_location_id:
            raise ValidationError('Source and destination locations must differ.')


class StockTransferLine(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='stock_transfer_lines')
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='transfer_lines')
    quantity = models.DecimalField(max_digits=14, decimal_places=3)


class StockMovement(models.Model):
    class Type(models.TextChoices):
        PURCHASE_RECEIPT = 'PURCHASE_RECEIPT', 'Purchase receipt'
        SALE = 'SALE', 'Sale'
        CUSTOMER_RETURN = 'CUSTOMER_RETURN', 'Customer return'
        SUPPLIER_RETURN = 'SUPPLIER_RETURN', 'Supplier return'
        ADJUSTMENT_IN = 'ADJUSTMENT_IN', 'Adjustment in'
        ADJUSTMENT_OUT = 'ADJUSTMENT_OUT', 'Adjustment out'
        TRANSFER_IN = 'TRANSFER_IN', 'Transfer in'
        TRANSFER_OUT = 'TRANSFER_OUT', 'Transfer out'
        REVERSAL = 'REVERSAL', 'Reversal'

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='stock_movements')
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='stock_movements')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_movements')
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=3)
    movement_type = models.CharField(max_length=20, choices=Type.choices)
    purchase_line = models.ForeignKey(PurchaseLine, null=True, blank=True, on_delete=models.PROTECT, related_name='stock_movements')
    sale_line = models.ForeignKey(SaleLine, null=True, blank=True, on_delete=models.PROTECT, related_name='stock_movements')
    sale_return_line = models.ForeignKey(SaleReturnLine, null=True, blank=True, on_delete=models.PROTECT, related_name='stock_movements')
    purchase_return_line = models.ForeignKey(PurchaseReturnLine, null=True, blank=True, on_delete=models.PROTECT, related_name='stock_movements')
    transfer = models.ForeignKey(StockTransfer, null=True, blank=True, on_delete=models.PROTECT, related_name='stock_movements')
    adjustment_reason = models.CharField(max_length=255, blank=True)
    unit_cost_snapshot = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['business', 'location', 'product', 'created_at'])]


class Payment(models.Model):
    class Direction(models.TextChoices):
        IN = 'IN', 'Money received'
        OUT = 'OUT', 'Money paid'

    class Method(models.TextChoices):
        CASH = 'CASH', 'Cash'
        BANK = 'BANK', 'Bank'
        MFS = 'MFS', 'Mobile financial service'
        OTHER = 'OTHER', 'Other'

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='payments')
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.PROTECT, related_name='payments')
    direction = models.CharField(max_length=3, choices=Direction.choices)
    payment_method = models.CharField(max_length=5, choices=Method.choices, default=Method.CASH)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateField()
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    reverses_payment = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='reversal_payments')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentAllocation(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='payment_allocations')
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name='allocations')
    sale = models.ForeignKey(Sale, null=True, blank=True, on_delete=models.PROTECT, related_name='payment_allocations')
    purchase = models.ForeignKey(Purchase, null=True, blank=True, on_delete=models.PROTECT, related_name='payment_allocations')
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [models.CheckConstraint(condition=(Q(sale__isnull=False, purchase__isnull=True) | Q(sale__isnull=True, purchase__isnull=False)), name='allocation_exactly_one_document')]

    def clean(self):
        if bool(self.sale_id) == bool(self.purchase_id):
            raise ValidationError('Allocation must reference exactly one sale or purchase.')


class Expense(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='expenses')
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT, related_name='expenses')
    category = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    expense_date = models.DateField()
    payment_method = models.CharField(max_length=5, choices=Payment.Method.choices, default=Payment.Method.CASH)
    reference = models.CharField(max_length=100, blank=True)
    is_void = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)


class ActivityLog(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='activity_logs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=64)
    entity_id = models.UUIDField()
    summary = models.CharField(max_length=255, blank=True)
    before_data = models.JSONField(default=dict, blank=True)
    after_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['business', 'entity_type', 'entity_id', 'created_at'])]
