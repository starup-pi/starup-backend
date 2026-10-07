"""CSRF-protected session entry points and self-only identity access."""

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from starup_backend.common.throttling import enforce_auth_limit
from starup_backend.privacy.services import erase_account

from .serializers import (
    CsrfSerializer,
    LoginSerializer,
    MessageSerializer,
    PrivateAccountSerializer,
    RegistrationSerializer,
    private_account,
)
from .services import register_account


class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses=CsrfSerializer)
    def get(self, request):
        return Response(
            {
                "csrf_token": get_token(request),
                "policy_version": settings.PRIVACY_POLICY_VERSION,
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class RegistrationView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(request=RegistrationSerializer, responses={202: MessageSerializer})
    def post(self, request):
        enforce_auth_limit(request, scope="register", limit=5)
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        register_account(data=serializer.validated_data)
        return Response(
            {"message": "Solicitação de cadastro recebida."},
            status=status.HTTP_202_ACCEPTED,
        )


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses=CsrfSerializer)
    def post(self, request):
        enforce_auth_limit(request, scope="login")
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request,
            email=serializer.validated_data["email"].strip().lower(),
            password=serializer.validated_data["password"],
        )
        if user is None:
            raise AuthenticationFailed()
        login(request, user)
        return Response({"csrf_token": get_token(request)})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=204)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=PrivateAccountSerializer)
    def get(self, request):
        return Response(PrivateAccountSerializer(private_account(request.user)).data)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request):
        erase_account(actor=request.user)
        logout(request)
        return Response(status=204)
