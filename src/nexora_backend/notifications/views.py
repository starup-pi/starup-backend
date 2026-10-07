"""Push capabilities are visible only to their owner."""

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    PushConfigSerializer,
    PushSubscriptionResultSerializer,
    PushSubscriptionSerializer,
)
from .services import subscribe, unsubscribe


class PushConfigView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=PushConfigSerializer)
    def get(self, request):
        return Response({"public_key": settings.VAPID_PUBLIC_KEY})


class PushSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PushSubscriptionSerializer,
        responses={201: PushSubscriptionResultSerializer},
    )
    def post(self, request):
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = subscribe(actor=request.user, data=serializer.validated_data)
        return Response({"id": subscription.id}, status=201)


class PushSubscriptionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, subscription_id):
        unsubscribe(actor=request.user, subscription_id=subscription_id)
        return Response(status=204)
