"""Public startup directory and controlled owner updates."""

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .selectors import public_startups
from .serializers import PublicStartupSerializer, StartupUpdateSerializer
from .services import update_startup


class StartupViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    lookup_value_converter = "uuid"
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PublicStartupSerializer

    def get_queryset(self):
        return public_startups()

    def get_object(self):
        try:
            return self.get_queryset().get(id=self.kwargs["pk"])
        except (ValueError, TypeError):
            raise NotFound() from None
        except self.get_queryset().model.DoesNotExist:
            raise NotFound() from None


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
