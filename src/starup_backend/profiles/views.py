"""Public startup directory and controlled owner updates."""

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from starup_backend.demands.serializers import DemandSerializer

from .selectors import (
    public_client_demands,
    public_clients,
    public_startup_demands,
    public_startups,
)
from .serializers import (
    PublicClientSerializer,
    PublicHistoryQuerySerializer,
    PublicStartupSerializer,
    StartupUpdateSerializer,
)
from .services import update_startup


class PublicProfileViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    lookup_value_converter = "uuid"
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_object(self):
        try:
            return self.get_queryset().get(id=self.kwargs["pk"])
        except (ValueError, TypeError):
            raise NotFound() from None
        except self.get_queryset().model.DoesNotExist:
            raise NotFound() from None

    @extend_schema(
        parameters=[PublicHistoryQuerySerializer],
        responses=DemandSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def demands(self, request, pk=None):
        profile = self.get_object()
        query = PublicHistoryQuerySerializer(data=request.query_params.dict())
        query.is_valid(raise_exception=True)
        queryset = self.history_queryset(profile["id"])
        if "status" in query.validated_data:
            queryset = queryset.filter(status=query.validated_data["status"])
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(DemandSerializer(page, many=True).data)


class StartupViewSet(mixins.ListModelMixin, PublicProfileViewSet):
    serializer_class = PublicStartupSerializer
    history_queryset = staticmethod(public_startup_demands)

    def get_queryset(self):
        return public_startups()


class ClientViewSet(PublicProfileViewSet):
    serializer_class = PublicClientSerializer
    history_queryset = staticmethod(public_client_demands)

    def get_queryset(self):
        return public_clients()


class OwnStartupViewSet(viewsets.GenericViewSet):
    lookup_value_converter = "uuid"
    serializer_class = StartupUpdateSerializer

    @extend_schema(request=StartupUpdateSerializer, responses={204: None})
    def partial_update(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_startup(
            actor=request.user, startup_id=pk, data=serializer.validated_data
        )
        return Response(status=204)
