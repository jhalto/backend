from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from ..models import ActivityLog, BusinessUser, Payment, PaymentAllocation, Sale, SaleReturn, SaleReturnLine, StockMovement
from .common import _assert_member, _assert_same_business, _money, on_hand


@transaction.atomic
def complete_sale(sale, *, actor=None, payment_amount=Decimal('0'), payment_method=Payment.Method.CASH):
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status != Sale.Status.DRAFT:
        raise ValidationError('Only draft sales can be completed.')
    _assert_member(sale.business, actor)
    _assert_same_business(sale.business, sale.location, sale.customer)
    lines = list(sale.lines.select_related('product'))
    if not lines:
        raise ValidationError('A sale must contain at least one line.')
    for line in lines:
        _assert_same_business(sale.business, line.product)
        if line.quantity <= 0:
            raise ValidationError('Sale quantities must be positive.')
        if on_hand(sale.business, sale.location, line.product) < line.quantity:
            raise ValidationError(f'Insufficient stock for {line.product.name}.')
    sale.status = Sale.Status.COMPLETED
    sale.save(update_fields=['status', 'updated_at'])
    for line in lines:
        StockMovement.objects.create(
            business=sale.business, location=sale.location, product=line.product,
            quantity_delta=-line.quantity, movement_type=StockMovement.Type.SALE,
            sale_line=line, created_by=actor,
        )
    amount = Decimal(payment_amount)
    if amount < 0 or amount > sale.grand_total:
        raise ValidationError('Payment must be between zero and the sale total.')
    if amount:
        payment = Payment.objects.create(
            business=sale.business, contact=sale.customer, direction=Payment.Direction.IN,
            payment_method=payment_method, amount=amount, payment_date=sale.sale_date,
            created_by=actor,
        )
        PaymentAllocation.objects.create(
            business=sale.business, payment=payment, sale=sale, amount=amount,
        )
    ActivityLog.objects.create(
        business=sale.business, actor=actor, action='SALE_COMPLETED',
        entity_type='Sale', entity_id=sale.pk, summary=f'Sale {sale.sale_number} completed',
    )
    return sale


@transaction.atomic
def return_sale(sale, *, return_number, return_date, items, actor=None, reason=''):
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    _assert_member(sale.business, actor)
    if sale.status not in (Sale.Status.COMPLETED, Sale.Status.PARTIALLY_RETURNED):
        raise ValidationError('Only completed sales can be returned.')
    lines = {line.pk: line for line in sale.lines.select_related('product')}
    if not items:
        raise ValidationError('At least one return line is required.')
    prepared = []
    total = Decimal('0')
    combined = {}
    for item in items:
        combined[item['sale_line_id']] = combined.get(item['sale_line_id'], Decimal('0')) + Decimal(item['quantity'])
    for line_id, quantity in combined.items():
        line = lines.get(line_id)
        if line is None or quantity <= 0:
            raise ValidationError('Return line must refer to a sale line and have positive quantity.')
        already_returned = line.return_lines.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        if quantity > line.quantity - already_returned:
            raise ValidationError(f'Return quantity exceeds the unreturned quantity for {line.product_name_snapshot}.')
        line_total = _money(line.line_total * quantity / line.quantity)
        prepared.append((line, quantity, line_total))
        total += line_total
    result = SaleReturn.objects.create(
        business=sale.business, sale=sale, return_number=return_number,
        return_date=return_date, total=total, reason=reason, created_by=actor,
    )
    for line, quantity, line_total in prepared:
        returned = SaleReturnLine.objects.create(
            business=sale.business, sale_return=result, sale_line=line, product=line.product,
            quantity=quantity, unit_price=line.unit_price, line_total=line_total,
            product_name_snapshot=line.product_name_snapshot, sku_snapshot=line.sku_snapshot,
        )
        StockMovement.objects.create(
            business=sale.business, location=sale.location, product=line.product,
            quantity_delta=quantity, movement_type=StockMovement.Type.CUSTOMER_RETURN,
            sale_return_line=returned, created_by=actor,
        )
    returned_qty = sum((line.return_lines.aggregate(total=Sum('quantity'))['total'] or Decimal('0') for line in lines.values()), Decimal('0'))
    sold_qty = sum((line.quantity for line in lines.values()), Decimal('0'))
    sale.status = Sale.Status.RETURNED if returned_qty >= sold_qty else Sale.Status.PARTIALLY_RETURNED
    sale.save(update_fields=['status', 'updated_at'])
    ActivityLog.objects.create(
        business=sale.business, actor=actor, action='SALE_RETURNED', entity_type='SaleReturn',
        entity_id=result.pk, summary=f'Return {return_number} recorded for sale {sale.sale_number}',
    )
    return result
