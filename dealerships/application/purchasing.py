from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from ..models import ActivityLog, BusinessUser, Payment, PaymentAllocation, Purchase, PurchaseReturn, PurchaseReturnLine, StockMovement
from .common import _assert_member, _assert_same_business, _money, on_hand


@transaction.atomic
def receive_purchase(purchase, *, actor=None, payment_amount=Decimal('0'), payment_method=Payment.Method.CASH):
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.status != Purchase.Status.DRAFT:
        raise ValidationError('Only draft purchases can be received.')
    _assert_member(purchase.business, actor)
    _assert_same_business(purchase.business, purchase.location, purchase.supplier)
    lines = list(purchase.lines.select_related('product'))
    if not lines:
        raise ValidationError('A purchase must contain at least one line.')
    for line in lines:
        _assert_same_business(purchase.business, line.product)
        if line.quantity <= 0:
            raise ValidationError('Purchase quantities must be positive.')
    purchase.status = Purchase.Status.RECEIVED
    purchase.save(update_fields=['status', 'updated_at'])
    for line in lines:
        StockMovement.objects.create(
            business=purchase.business, location=purchase.location, product=line.product,
            quantity_delta=line.quantity, movement_type=StockMovement.Type.PURCHASE_RECEIPT,
            purchase_line=line, unit_cost_snapshot=line.unit_cost, created_by=actor,
        )
    amount = Decimal(payment_amount)
    if amount < 0 or amount > purchase.grand_total:
        raise ValidationError('Payment must be between zero and the purchase total.')
    if amount:
        payment = Payment.objects.create(
            business=purchase.business, contact=purchase.supplier, direction=Payment.Direction.OUT,
            payment_method=payment_method, amount=amount, payment_date=purchase.purchase_date,
            created_by=actor,
        )
        PaymentAllocation.objects.create(
            business=purchase.business, payment=payment, purchase=purchase, amount=amount,
        )
    ActivityLog.objects.create(
        business=purchase.business, actor=actor, action='PURCHASE_RECEIVED',
        entity_type='Purchase', entity_id=purchase.pk,
        summary=f'Purchase {purchase.purchase_number} received',
    )
    return purchase


@transaction.atomic
def return_purchase(purchase, *, return_number, return_date, items, actor=None, reason=''):
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
    _assert_member(purchase.business, actor)
    if purchase.status not in (Purchase.Status.RECEIVED, Purchase.Status.PARTIALLY_RETURNED):
        raise ValidationError('Only received purchases can be returned.')
    lines = {line.pk: line for line in purchase.lines.select_related('product')}
    if not items:
        raise ValidationError('At least one return line is required.')
    prepared = []
    total = Decimal('0')
    combined = {}
    for item in items:
        combined[item['purchase_line_id']] = combined.get(item['purchase_line_id'], Decimal('0')) + Decimal(item['quantity'])
    for line_id, quantity in combined.items():
        line = lines.get(line_id)
        if line is None or quantity <= 0:
            raise ValidationError('Return line must refer to a purchase line and have positive quantity.')
        already_returned = line.return_lines.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        if quantity > line.quantity - already_returned:
            raise ValidationError(f'Return quantity exceeds the unreturned quantity for {line.product_name_snapshot}.')
        if on_hand(purchase.business, purchase.location, line.product) < quantity:
            raise ValidationError(f'Insufficient stock to return {line.product_name_snapshot}.')
        line_total = _money(line.line_total * quantity / line.quantity)
        prepared.append((line, quantity, line_total))
        total += line_total
    result = PurchaseReturn.objects.create(
        business=purchase.business, purchase=purchase, return_number=return_number,
        return_date=return_date, total=total, reason=reason, created_by=actor,
    )
    for line, quantity, line_total in prepared:
        returned = PurchaseReturnLine.objects.create(
            business=purchase.business, purchase_return=result, purchase_line=line,
            product=line.product, quantity=quantity, unit_cost=line.unit_cost,
            line_total=line_total, product_name_snapshot=line.product_name_snapshot,
            sku_snapshot=line.sku_snapshot,
        )
        StockMovement.objects.create(
            business=purchase.business, location=purchase.location, product=line.product,
            quantity_delta=-quantity, movement_type=StockMovement.Type.SUPPLIER_RETURN,
            purchase_return_line=returned, unit_cost_snapshot=line.unit_cost, created_by=actor,
        )
    returned_qty = sum((line.return_lines.aggregate(total=Sum('quantity'))['total'] or Decimal('0') for line in lines.values()), Decimal('0'))
    received_qty = sum((line.quantity for line in lines.values()), Decimal('0'))
    purchase.status = Purchase.Status.RETURNED if returned_qty >= received_qty else Purchase.Status.PARTIALLY_RETURNED
    purchase.save(update_fields=['status', 'updated_at'])
    ActivityLog.objects.create(
        business=purchase.business, actor=actor, action='PURCHASE_RETURNED', entity_type='PurchaseReturn',
        entity_id=result.pk, summary=f'Return {return_number} recorded for purchase {purchase.purchase_number}',
    )
    return result
