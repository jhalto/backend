from django.contrib.auth import authenticate, get_user_model, logout as django_logout
from django.db import transaction
from rest_framework.authtoken.models import Token
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...application import create_business_for_owner
from ...models import BusinessUser


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    business_name = serializers.CharField(max_length=200)
    location_name = serializers.CharField(max_length=120, required=False, default='Main location')

    def validate_username(self, value):
        user_model = get_user_model()
        if user_model.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already in use.')
        return value

    @transaction.atomic
    def create(self, validated_data):
        user_model = get_user_model()
        username = validated_data['username']
        user = user_model.objects.create_user(
            username=username, email=validated_data['email'], password=validated_data['password'],
        )
        business = create_business_for_owner(
            name=validated_data['business_name'], owner=user,
            location_name=validated_data['location_name'],
        )
        token, _ = Token.objects.get_or_create(user=user)
        return user, business, token


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


@api_view(['POST'])
@permission_classes([])
def signup(request):
    serializer = SignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user, business, token = serializer.save()
    return Response({
        'token': token.key,
        'user': {'id': user.pk, 'username': user.get_username(), 'email': user.email},
        'business': {'id': str(business.pk), 'name': business.name},
        'message': 'Account created. The default location is ready.',
    }, status=201)


@api_view(['POST'])
@permission_classes([])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        request=request, username=serializer.validated_data['username'],
        password=serializer.validated_data['password'],
    )
    if user is None or not user.is_active:
        raise AuthenticationFailed('Invalid username or password.')
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': {'id': user.pk, 'username': user.get_username(), 'email': user.email},
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    if isinstance(request.auth, Token):
        request.auth.delete()
    if request.auth is None:
        django_logout(request)
    return Response(status=204)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    user = request.user
    return Response({
        'id': user.pk, 'username': user.get_username(), 'email': user.email,
        'businesses': list(BusinessUser.objects.filter(
            user=user, is_active=True, business__is_active=True,
        ).values('business_id', 'business__name', 'role')),
    })
