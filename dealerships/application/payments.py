from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from ..models import ActivityLog, BusinessUser, Payment, PaymentAllocation, Purchase, Sale
from .common import _assert_member, _assert_same_business, _remaining_document_balance


@transaction.atomic
def allocate_payment(payment, *, amount, actor=None, sale=None, purchase=None):
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    _assert_member(payment.business, actor)
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError('Allocation amount must be greater than zero.')
    if bool(sale) == bool(purchase):
        raise ValidationError('Choose exactly one sale or purchase.')
    document = sale or purchase
    if sale:
        sale = Sale.objects.select_for_update().get(pk=sale.pk)
        document = sale
    else:
        purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
        document = purchase
    _assert_same_business(payment.business, payment.contact, document)
    if sale:
        if payment.direction != Payment.Direction.IN or sale.status not in (Sale.Status.COMPLETED, Sale.Status.PARTIALLY_RETURNED):
            raise ValidationError('Incoming payments can only be allocated to active sales.')
        if payment.contact_id and payment.contact_id != sale.customer_id:
            raise ValidationError('Payment contact does not match the sale customer.')
    else:
        if payment.direction != Payment.Direction.OUT or purchase.status not in (Purchase.Status.RECEIVED, Purchase.Status.PARTIALLY_RETURNED):
            raise ValidationError('Outgoing payments can only be allocated to received purchases.')
        if payment.contact_id and payment.contact_id != purchase.supplier_id:
            raise ValidationError('Payment contact does not match the purchase supplier.')
    allocated = payment.allocations.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    if amount > payment.amount - allocated:
        raise ValidationError('Allocation exceeds the unallocated payment amount.')
    if amount > _remaining_document_balance(document, is_sale=bool(sale)):
        raise ValidationError('Allocation exceeds the document balance after returns.')
    allocation = PaymentAllocation.objects.create(
        business=payment.business, payment=payment, sale=sale, purchase=purchase, amount=amount,
    )
    ActivityLog.objects.create(
        business=payment.business, actor=actor, action='PAYMENT_ALLOCATED',
        entity_type='Payment', entity_id=payment.pk,
        summary=f'Allocated {amount} to {"sale" if sale else "purchase"} {document.sale_number if sale else document.purchase_number}',
    )
    return allocation
