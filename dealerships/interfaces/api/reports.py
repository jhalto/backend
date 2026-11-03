from decimal import Decimal
from django.db.models import Sum
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import BusinessUser, Expense, PaymentAllocation, Purchase, Sale, StockMovement


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_businesses(request):
    memberships = BusinessUser.objects.filter(
        user=request.user, is_active=True, business__is_active=True,
    ).select_related('business').order_by('business__name')
    return Response([
        {
            'id': str(m.business_id), 'name': m.business.name, 'role': m.role,
            'currency_code': m.business.currency_code,
            'locations': list(m.business.locations.filter(is_active=True).values('id', 'name', 'code', 'kind', 'is_default')),
        }
        for m in memberships
    ])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def business_summary(request, business_id):
    membership = BusinessUser.objects.filter(
        business_id=business_id, user=request.user, is_active=True,
        business__is_active=True,
    ).select_related('business').first()
    if membership is None:
        raise PermissionDenied('You do not have access to this dealership.')
    business = membership.business
    start = parse_date(request.query_params.get('start', ''))
    end = parse_date(request.query_params.get('end', ''))
    sales = Sale.objects.filter(business=business, status__in=[Sale.Status.COMPLETED, Sale.Status.PARTIALLY_RETURNED, Sale.Status.RETURNED])
    purchases = Purchase.objects.filter(business=business, status__in=[Purchase.Status.RECEIVED, Purchase.Status.PARTIALLY_RETURNED, Purchase.Status.RETURNED])
    expenses = Expense.objects.filter(business=business, is_void=False)
    if start:
        sales, purchases, expenses = sales.filter(sale_date__gte=start), purchases.filter(purchase_date__gte=start), expenses.filter(expense_date__gte=start)
    if end:
        sales, purchases, expenses = sales.filter(sale_date__lte=end), purchases.filter(purchase_date__lte=end), expenses.filter(expense_date__lte=end)
    stock = StockMovement.objects.filter(business=business).values('location_id', 'location__name', 'product_id', 'product__sku', 'product__name').annotate(quantity=Sum('quantity_delta')).order_by('location__name', 'product__name')
    sales_total = sales.aggregate(total=Sum('grand_total'))['total'] or Decimal('0')
    purchases_total = purchases.aggregate(total=Sum('grand_total'))['total'] or Decimal('0')
    sales_returned = business.sale_returns.filter(sale__in=sales).aggregate(total=Sum('total'))['total'] or Decimal('0')
    purchases_returned = business.purchase_returns.filter(purchase__in=purchases).aggregate(total=Sum('total'))['total'] or Decimal('0')
    sales_paid = PaymentAllocation.objects.filter(business=business, sale__in=sales).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    purchases_paid = PaymentAllocation.objects.filter(business=business, purchase__in=purchases).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    return Response({
        'business': {'id': str(business.pk), 'name': business.name, 'currency_code': business.currency_code},
        'period': {'start': start, 'end': end},
        'sales_count': sales.count(),
        'sales_total': sales_total - sales_returned,
        'purchases_count': purchases.count(),
        'purchases_total': purchases_total - purchases_returned,
        'expenses_total': expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0'),
        'customer_due_total': sales_total - sales_returned - sales_paid,
        'supplier_due_total': purchases_total - purchases_returned - purchases_paid,
        'stock': list(stock),
    })
