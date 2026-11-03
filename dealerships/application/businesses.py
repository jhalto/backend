from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import Business, BusinessUser, Location


def create_business_for_owner(*, name, owner, location_name='Main location'):
    """Create tenant, owner membership, and its required default stock location."""
    if not owner or not owner.is_authenticated:
        raise ValidationError('An authenticated owner is required.')
    with transaction.atomic():
        business = Business.objects.create(name=name)
        BusinessUser.objects.create(business=business, user=owner, role=BusinessUser.Role.OWNER)
        Location.objects.create(
            business=business, name=location_name, code='MAIN', is_default=True,
        )
    return business
