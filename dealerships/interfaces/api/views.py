from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...application import allocate_payment, complete_sale, complete_transfer, on_hand, receive_purchase, return_purchase, return_sale
from ...models import BusinessUser, Contact, Expense, Location, Payment, PaymentAllocation, Product, ProductCategory, Purchase, Sale, StockMovement, StockTransfer
from .serializers import (AllocationInputSerializer, CategorySerializer, ContactSerializer, ExpenseSerializer, LocationSerializer, PaymentSerializer, ProductSerializer, PurchaseActionSerializer, PurchaseSerializer, ReturnInputSerializer, SaleActionSerializer, SaleSerializer, TransferSerializer)


class BusinessScopeMixin:
    permission_classes = [IsAuthenticated]

    def get_business(self):
        business_id = self.kwargs['business_id']
        membership = BusinessUser.objects.filter(
            business_id=business_id, user=self.request.user, is_active=True,
            business__is_active=True,
        ).select_related('business').first()
        if not membership:
            raise PermissionDenied('You do not have access to this dealership.')
        return membership.business

    def get_queryset(self):
        return super().get_queryset().filter(business=self.get_business())

    def perform_create(self, serializer):
        serializer.save(business=self.get_business())


class LocationViewSet(BusinessScopeMixin, viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer


class CategoryViewSet(BusinessScopeMixin, viewsets.ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = CategorySerializer


class ProductViewSet(BusinessScopeMixin, viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer

    @action(detail=False, methods=['get'])
    def stock(self, request, business_id=None):
        business = self.get_business()
        location_id = request.query_params.get('location')
        movements = StockMovement.objects.filter(business=business)
        if location_id:
            if not Location.objects.filter(business=business, pk=location_id).exists():
                raise ValidationError({'location': 'Unknown location for this dealership.'})
            movements = movements.filter(location_id=location_id)
        rows = movements.values('product_id', 'product__sku', 'product__name', 'location_id', 'location__name').annotate(quantity=Sum('quantity_delta')).order_by('product__name', 'location__name')
        return Response(list(rows))


class ContactViewSet(BusinessScopeMixin, viewsets.ModelViewSet):
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer


class PurchaseViewSet(BusinessScopeMixin, viewsets.ModelViewSet):
    queryset = Purchase.objects.select_related('supplier', 'location').prefetch_related('lines').all()
    serializer_class = PurchaseSerializer

    def perform_create(self, serializer):
        serializer.save(business=self.get_business(), created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def receive(self, request, business_id=None, pk=None):
        purchase = self.get_object()
        data = PurchaseActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            receive_purchase(purchase, actor=request.user, **data.validated_data)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(self.get_serializer(purchase).data)

    @action(detail=True, methods=['post'])
    def returns(self, request, business_id=None, pk=None):
        purchase = self.get_object()
        data = ReturnInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        payload = data.validated_data
        if purchase.returns.filter(return_number=payload['return_number']).exists():
            raise ValidationError({'return_number': 'This return number is already used for the purchase.'})
        try:
            result = return_purchase(
                purchase, return_number=payload['return_number'], return_date=payload['return_date'],
                reason=payload['reason'], actor=request.user,
                items=[{'purchase_line_id': item['line_id'], 'quantity': item['quantity']} for item in payload['items']],
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response({'id': result.pk, 'return_number': result.return_number, 'total': result.total, 'status': purchase.status}, status=201)


class SaleViewSet(BusinessScopeMixin, viewsets.ModelViewSet):
    queryset = Sale.objects.select_related('customer', 'location').prefetch_related('lines').all()
    serializer_class = SaleSerializer

    def perform_create(self, serializer):
        serializer.save(business=self.get_business(), created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def complete(self, request, business_id=None, pk=None):
        sale = self.get_object()
        data = SaleActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            complete_sale(sale, actor=request.user, **data.validated_data)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(self.get_serializer(sale).data)

    @action(detail=True, methods=['post'])
    def returns(self, request, business_id=None, pk=None):
        sale = self.get_object()
        data = ReturnInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        payload = data.validated_data
        if sale.returns.filter(return_number=payload['return_number']).exists():
            raise ValidationError({'return_number': 'This return number is already used for the sale.'})
        try:
            result = return_sale(
                sale, return_number=payload['return_number'], return_date=payload['return_date'],
                reason=payload['reason'], actor=request.user,
                items=[{'sale_line_id': item['line_id'], 'quantity': item['quantity']} for item in payload['items']],
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response({'id': result.pk, 'return_number': result.return_number, 'total': result.total, 'status': sale.status}, status=201)


class ExpenseViewSet(BusinessScopeMixin, viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer

    def perform_create(self, serializer):
        serializer.save(business=self.get_business(), created_by=self.request.user)


class PaymentViewSet(BusinessScopeMixin, viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('contact').all()
    serializer_class = PaymentSerializer

    def perform_create(self, serializer):
        serializer.save(business=self.get_business(), created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def allocate(self, request, business_id=None, pk=None):
        payment = self.get_object()
        data = AllocationInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        payload = data.validated_data
        sale = Sale.objects.filter(business=payment.business, pk=payload.get('sale_id')).first() if payload.get('sale_id') else None
        purchase = Purchase.objects.filter(business=payment.business, pk=payload.get('purchase_id')).first() if payload.get('purchase_id') else None
        if payload.get('sale_id') and sale is None or payload.get('purchase_id') and purchase is None:
            raise ValidationError('The selected document does not belong to this dealership.')
        try:
            allocation = allocate_payment(
                payment, amount=payload['amount'], actor=request.user, sale=sale, purchase=purchase,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response({'id': allocation.pk, 'payment_id': payment.pk, 'sale_id': allocation.sale_id,
                         'purchase_id': allocation.purchase_id, 'amount': allocation.amount}, status=201)


class StockTransferViewSet(BusinessScopeMixin, viewsets.ModelViewSet):
    queryset = StockTransfer.objects.prefetch_related('lines').all()
    serializer_class = TransferSerializer

    def perform_create(self, serializer):
        serializer.save(business=self.get_business(), created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def complete(self, request, business_id=None, pk=None):
        transfer = self.get_object()
        try:
            complete_transfer(transfer, actor=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response({'id': str(transfer.pk), 'status': transfer.status})
