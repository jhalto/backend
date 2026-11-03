from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from ...models import (Contact, Location, Payment, Product, ProductCategory, Purchase, PurchaseLine, Sale, SaleLine, StockTransfer, StockTransferLine, Expense)


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        exclude = ('business',)
        read_only_fields = ('id', 'created_at', 'updated_at')


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        exclude = ('business',)
        read_only_fields = ('id', 'created_at', 'updated_at')


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        exclude = ('business',)
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_category(self, value):
        if value and value.business_id != self.context['view'].get_business().pk:
            raise serializers.ValidationError('Category belongs to another dealership.')
        return value


class PurchaseLineInputSerializer(serializers.Serializer):
    product = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal('0.001'))
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'))
    discount_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False, default=Decimal('0'))
    tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False, default=Decimal('0'))

    def validate(self, attrs):
        if attrs['discount_amount'] > attrs['quantity'] * attrs['unit_cost']:
            raise serializers.ValidationError('Discount cannot exceed the line subtotal.')
        return attrs


class SaleLineInputSerializer(serializers.Serializer):
    product = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal('0.001'))
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False)
    discount_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False, default=Decimal('0'))
    tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False, default=Decimal('0'))

    def validate(self, attrs):
        if attrs.get('unit_price') is not None and attrs['discount_amount'] > attrs['quantity'] * attrs['unit_price']:
            raise serializers.ValidationError('Discount cannot exceed the line subtotal.')
        return attrs


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        exclude = ('business',)
        read_only_fields = ('id', 'created_at', 'updated_at')


class PurchaseSerializer(serializers.ModelSerializer):
    lines = serializers.SerializerMethodField()
    returns = serializers.SerializerMethodField()
    items = PurchaseLineInputSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Purchase
        exclude = ('business',)
        read_only_fields = ('id', 'status', 'created_at', 'updated_at', 'created_by')

    def validate(self, attrs):
        business = self.context['view'].get_business()
        if attrs.get('location') and attrs['location'].business_id != business.pk:
            raise serializers.ValidationError({'location': 'Location belongs to another dealership.'})
        if attrs.get('supplier') and attrs['supplier'].business_id != business.pk:
            raise serializers.ValidationError({'supplier': 'Supplier belongs to another dealership.'})
        if not self.initial_data.get('items'):
            raise serializers.ValidationError({'lines': 'At least one purchase line is required.'})
        return attrs

    def get_lines(self, obj):
        return list(obj.lines.values('id', 'product_id', 'product_name_snapshot', 'sku_snapshot', 'quantity', 'unit_cost', 'discount_amount', 'tax_amount', 'line_total'))

    def get_returns(self, obj):
        return list(obj.returns.values('id', 'return_number', 'return_date', 'total', 'reason'))

    @transaction.atomic
    def create(self, validated_data):
        from ...models import PurchaseLine
        lines = validated_data.pop('items', [])
        business = validated_data['business']
        validated_data.pop('subtotal', None)
        validated_data.pop('discount_total', None)
        validated_data.pop('tax_total', None)
        validated_data.pop('grand_total', None)
        purchase = Purchase.objects.create(created_by=self.context['request'].user, **validated_data)
        subtotal = Decimal('0')
        discounts = Decimal('0')
        taxes = Decimal('0')
        for row in lines:
            try:
                product = Product.objects.get(pk=row['product'], business=business)
            except Product.DoesNotExist as exc:
                raise serializers.ValidationError({'lines': 'A product does not belong to this dealership.'}) from exc
            quantity = row['quantity']
            unit_cost = row['unit_cost']
            PurchaseLine.objects.create(
                business=business, purchase=purchase, product=product, quantity=quantity,
                unit_cost=unit_cost, discount_amount=row.get('discount_amount', 0),
                tax_amount=row.get('tax_amount', 0), line_total=quantity * unit_cost - row.get('discount_amount', 0) + row.get('tax_amount', 0),
                product_name_snapshot=product.name, sku_snapshot=product.sku,
            )
            subtotal += quantity * unit_cost
            discounts += row.get('discount_amount', 0)
            taxes += row.get('tax_amount', 0)
        purchase.subtotal = subtotal
        purchase.discount_total = discounts
        purchase.tax_total = taxes
        purchase.grand_total = subtotal - discounts + taxes
        purchase.save(update_fields=['subtotal', 'discount_total', 'tax_total', 'grand_total', 'updated_at'])
        return purchase


class SaleSerializer(serializers.ModelSerializer):
    lines = serializers.SerializerMethodField()
    returns = serializers.SerializerMethodField()
    items = SaleLineInputSerializer(many=True, write_only=True, required=False)
    class Meta:
        model = Sale
        exclude = ('business',)
        read_only_fields = ('id', 'status', 'created_at', 'updated_at', 'created_by')

    def validate(self, attrs):
        business = self.context['view'].get_business()
        if attrs.get('location') and attrs['location'].business_id != business.pk:
            raise serializers.ValidationError({'location': 'Location belongs to another dealership.'})
        if attrs.get('customer') and attrs['customer'].business_id != business.pk:
            raise serializers.ValidationError({'customer': 'Customer belongs to another dealership.'})
        if not self.initial_data.get('items'):
            raise serializers.ValidationError({'lines': 'At least one sale line is required.'})
        return attrs

    def get_lines(self, obj):
        return list(obj.lines.values('id', 'product_id', 'product_name_snapshot', 'sku_snapshot', 'quantity', 'unit_price', 'discount_amount', 'tax_amount', 'line_total'))

    def get_returns(self, obj):
        return list(obj.returns.values('id', 'return_number', 'return_date', 'total', 'reason'))

    @transaction.atomic
    def create(self, validated_data):
        from ...models import SaleLine
        lines = validated_data.pop('items', [])
        business = validated_data['business']
        validated_data.pop('subtotal', None)
        validated_data.pop('discount_total', None)
        validated_data.pop('tax_total', None)
        validated_data.pop('grand_total', None)
        sale = Sale.objects.create(created_by=self.context['request'].user, **validated_data)
        subtotal = Decimal('0')
        discounts = Decimal('0')
        taxes = Decimal('0')
        for row in lines:
            try:
                product = Product.objects.get(pk=row['product'], business=business)
            except Product.DoesNotExist as exc:
                raise serializers.ValidationError({'lines': 'A product does not belong to this dealership.'}) from exc
            quantity = row['quantity']
            unit_price = row.get('unit_price', product.selling_price)
            SaleLine.objects.create(
                business=business, sale=sale, product=product, quantity=quantity,
                unit_price=unit_price, discount_amount=row.get('discount_amount', 0),
                tax_amount=row.get('tax_amount', 0), line_total=quantity * unit_price - row.get('discount_amount', 0) + row.get('tax_amount', 0),
                product_name_snapshot=product.name, sku_snapshot=product.sku,
            )
            subtotal += quantity * unit_price
            discounts += row.get('discount_amount', 0)
            taxes += row.get('tax_amount', 0)
        sale.subtotal = subtotal
        sale.discount_total = discounts
        sale.tax_total = taxes
        sale.grand_total = subtotal - discounts + taxes
        sale.save(update_fields=['subtotal', 'discount_total', 'tax_total', 'grand_total', 'updated_at'])
        return sale


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        exclude = ('business',)
        read_only_fields = ('id', 'is_void', 'created_at', 'updated_at', 'created_by')

    def validate_location(self, value):
        if value and value.business_id != self.context['view'].get_business().pk:
            raise serializers.ValidationError('Location belongs to another dealership.')
        return value


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        exclude = ('business',)
        read_only_fields = ('id', 'created_at', 'created_by', 'reverses_payment')

    def validate(self, attrs):
        business = self.context['view'].get_business()
        contact = attrs.get('contact')
        if contact and contact.business_id != business.pk:
            raise serializers.ValidationError({'contact': 'Contact belongs to another dealership.'})
        if attrs.get('amount', Decimal('0')) <= 0:
            raise serializers.ValidationError({'amount': 'Payment amount must be greater than zero.'})
        return attrs


class TransferLineInputSerializer(serializers.Serializer):
    product = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal('0.001'))


class TransferSerializer(serializers.ModelSerializer):
    items = TransferLineInputSerializer(many=True, write_only=True, required=False)
    lines = serializers.SerializerMethodField()

    class Meta:
        model = StockTransfer
        exclude = ('business',)
        read_only_fields = ('id', 'status', 'created_at', 'updated_at', 'created_by')

    def validate(self, attrs):
        business = self.context['view'].get_business()
        source = attrs.get('source_location')
        destination = attrs.get('destination_location')
        if source and source.business_id != business.pk:
            raise serializers.ValidationError({'source_location': 'Location belongs to another dealership.'})
        if destination and destination.business_id != business.pk:
            raise serializers.ValidationError({'destination_location': 'Location belongs to another dealership.'})
        if source and destination and source.pk == destination.pk:
            raise serializers.ValidationError('Source and destination locations must differ.')
        if not self.initial_data.get('items'):
            raise serializers.ValidationError({'items': 'At least one transfer line is required.'})
        return attrs

    def get_lines(self, obj):
        return list(obj.lines.values('id', 'product_id', 'product__name', 'quantity'))

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop('items')
        business = validated_data['business']
        transfer = StockTransfer.objects.create(created_by=self.context['request'].user, **validated_data)
        for item in lines:
            try:
                product = Product.objects.get(pk=item['product'], business=business)
            except Product.DoesNotExist as exc:
                raise serializers.ValidationError({'items': 'A product does not belong to this dealership.'}) from exc
            StockTransferLine.objects.create(business=business, transfer=transfer, product=product, quantity=item['quantity'])
        return transfer


class PurchaseActionSerializer(serializers.Serializer):
    payment_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, default=Decimal('0'))
    payment_method = serializers.ChoiceField(choices=Payment.Method.choices, required=False, default=Payment.Method.CASH)


class SaleActionSerializer(serializers.Serializer):
    payment_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, default=Decimal('0'))
    payment_method = serializers.ChoiceField(choices=Payment.Method.choices, required=False, default=Payment.Method.CASH)


class ReturnLineInputSerializer(serializers.Serializer):
    line_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal('0.001'))


class ReturnInputSerializer(serializers.Serializer):
    return_number = serializers.CharField(max_length=40)
    return_date = serializers.DateField()
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    items = ReturnLineInputSerializer(many=True, allow_empty=False)


class AllocationInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    sale_id = serializers.UUIDField(required=False)
    purchase_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        if bool(attrs.get('sale_id')) == bool(attrs.get('purchase_id')):
            raise serializers.ValidationError('Supply exactly one of sale_id or purchase_id.')
        return attrs
