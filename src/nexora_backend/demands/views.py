"""Demand views delegate all writes to services."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from nexora_backend.common.permissions import ClientWritePermission

from .models import Category
from .selectors import demand_projection
from .serializers import (
    CategorySerializer,
    DemandQuerySerializer,
    DemandSerializer,
    DemandWriteSerializer,
)
from .services import cancel_demand, create_demand, update_demand


class CategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    authentication_classes = []
    permission_classes = [AllowAny]
    queryset = Category.objects.order_by("name", "id")
    serializer_class = CategorySerializer


@extend_schema_view(list=extend_schema(parameters=[DemandQuerySerializer]))
class DemandViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    lookup_value_converter = "uuid"
    permission_classes = [ClientWritePermission]
    serializer_class = DemandSerializer
    lookup_field = "id"
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        queryset = demand_projection(self.request.user)
        if self.action != "list":
            return queryset
        query = DemandQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        if query.validated_data["mine"]:
            if not self.request.user.is_authenticated:
                return queryset.none()
            queryset = queryset.filter(client__user_id=self.request.user.pk)
        for field in ("visibility", "status"):
            if field in query.validated_data:
                queryset = queryset.filter(**{field: query.validated_data[field]})
        return queryset

    @extend_schema(request=DemandWriteSerializer, responses={201: DemandSerializer})
    def create(self, request):
        serializer = DemandWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        demand = create_demand(actor=request.user, data=serializer.validated_data)
        result = self.get_queryset().get(id=demand.id)
        return Response(DemandSerializer(result).data, status=201)

    @extend_schema(request=DemandWriteSerializer, responses=DemandSerializer)
    def partial_update(self, request, pk=None):
        serializer = DemandWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        update_demand(actor=request.user, demand_id=pk, data=serializer.validated_data)
        return Response(DemandSerializer(self.get_object()).data)

    @extend_schema(request=None, responses=DemandSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        cancel_demand(actor=request.user, demand_id=pk)
        return Response(DemandSerializer(self.get_object()).data)
