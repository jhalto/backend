from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import ActivityLog, BusinessUser, StockMovement, StockTransfer
from .common import _assert_member, _assert_same_business, on_hand


@transaction.atomic
def complete_transfer(transfer, *, actor=None):
    transfer = StockTransfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.status != StockTransfer.Status.DRAFT:
        raise ValidationError('Only draft transfers can be completed.')
    _assert_member(transfer.business, actor)
    _assert_same_business(transfer.business, transfer.source_location, transfer.destination_location)
    if transfer.source_location_id == transfer.destination_location_id:
        raise ValidationError('Source and destination locations must differ.')
    lines = list(transfer.lines.select_related('product'))
    if not lines:
        raise ValidationError('A transfer must contain at least one line.')
    for line in lines:
        _assert_same_business(transfer.business, line.product)
        if line.quantity <= 0:
            raise ValidationError('Transfer quantities must be positive.')
        if on_hand(transfer.business, transfer.source_location, line.product) < line.quantity:
            raise ValidationError(f'Insufficient stock for {line.product.name}.')
    transfer.status = StockTransfer.Status.COMPLETED
    transfer.save(update_fields=['status', 'updated_at'])
    for line in lines:
        StockMovement.objects.bulk_create([
            StockMovement(
                business=transfer.business, location=transfer.source_location,
                product=line.product, quantity_delta=-line.quantity,
                movement_type=StockMovement.Type.TRANSFER_OUT, transfer=transfer, created_by=actor,
            ),
            StockMovement(
                business=transfer.business, location=transfer.destination_location,
                product=line.product, quantity_delta=line.quantity,
                movement_type=StockMovement.Type.TRANSFER_IN, transfer=transfer, created_by=actor,
            ),
        ])
    ActivityLog.objects.create(
        business=transfer.business, actor=actor, action='STOCK_TRANSFER_COMPLETED',
        entity_type='StockTransfer', entity_id=transfer.pk,
        summary=f'Transfer {transfer.transfer_number} completed',
    )
    return transfer
