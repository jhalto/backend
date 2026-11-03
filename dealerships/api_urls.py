from rest_framework.routers import DefaultRouter

from .interfaces.api.auth import current_user, login_view, logout_view, signup
from .interfaces.api.reports import business_summary, my_businesses
from .interfaces.api.views import (
    CategoryViewSet, ContactViewSet, ExpenseViewSet, LocationViewSet,
    PaymentViewSet, ProductViewSet, PurchaseViewSet, SaleViewSet,
    StockTransferViewSet,
)
from django.urls import path


class BusinessRouter(DefaultRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trailing_slash = '/'


router = BusinessRouter()
router.register(r'businesses/(?P<business_id>[^/.]+)/locations', LocationViewSet, basename='locations')
router.register(r'businesses/(?P<business_id>[^/.]+)/categories', CategoryViewSet, basename='categories')
router.register(r'businesses/(?P<business_id>[^/.]+)/products', ProductViewSet, basename='products')
router.register(r'businesses/(?P<business_id>[^/.]+)/contacts', ContactViewSet, basename='contacts')
router.register(r'businesses/(?P<business_id>[^/.]+)/purchases', PurchaseViewSet, basename='purchases')
router.register(r'businesses/(?P<business_id>[^/.]+)/sales', SaleViewSet, basename='sales')
router.register(r'businesses/(?P<business_id>[^/.]+)/expenses', ExpenseViewSet, basename='expenses')
router.register(r'businesses/(?P<business_id>[^/.]+)/transfers', StockTransferViewSet, basename='transfers')
router.register(r'businesses/(?P<business_id>[^/.]+)/payments', PaymentViewSet, basename='payments')

urlpatterns = router.urls + [
    path('auth/signup/', signup, name='api-signup'),
    path('auth/login/', login_view, name='api-login'),
    path('auth/logout/', logout_view, name='api-logout'),
    path('auth/me/', current_user, name='api-current-user'),
    path('me/businesses/', my_businesses, name='my-businesses'),
    path('businesses/<uuid:business_id>/summary/', business_summary, name='business-summary'),
]
