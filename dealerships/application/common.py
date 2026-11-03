from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Sum

from ..models import PaymentAllocation, StockMovement


def _assert_member(business, user):
    if user is not None and not BusinessUser.objects.filter(business=business, user=user, is_active=True).exists():
        raise ValidationError('User is not an active member of this dealership.')


def _assert_same_business(business, *objects):
    if any(obj is not None and obj.business_id != business.pk for obj in objects):
        raise ValidationError('All records in an operation must belong to the same dealership.')


def on_hand(business, location, product):
    """Return ledger-derived stock; the ledger remains the source of truth."""
    return StockMovement.objects.filter(
        business=business, location=location, product=product
    ).aggregate(total=Sum('quantity_delta'))['total'] or Decimal('0')


def _money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _remaining_document_balance(document, *, is_sale):
    allocation_field = 'sale' if is_sale else 'purchase'
    allocations = PaymentAllocation.objects.filter(**{f'{allocation_field}__id': document.pk}).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    returns = document.returns.aggregate(total=Sum('total'))['total'] or Decimal('0')
    return document.grand_total - allocations - returns
